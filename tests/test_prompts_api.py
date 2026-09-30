"""A few HTTP-level tests: routing and error-to-status mapping. Logic is tested in test_prompts_service."""


def test_full_prompt_flow_over_http(client):
    prompt = client.post("/prompts", json={"name": "refund-reply"}).json()
    pid = prompt["id"]

    assert client.post(f"/prompts/{pid}/versions", json={"template": "Reply: {message}"}).status_code == 201
    assert client.post(f"/prompts/{pid}/versions", json={"template": "Responde: {message}"}).status_code == 201
    assert client.get(f"/prompts/{pid}/versions/2").json()["variables"] == ["message"]
    assert len(client.get(f"/prompts/{pid}/versions").json()) == 2
    assert client.get(f"/prompts/{pid}/versions/1/diff/2").json()["added"] == 1

    tc = client.post(f"/prompts/{pid}/test-cases", json={
        "name": "spanish", "inputs": {"message": "hola"},
        "checks": [{"type": "contains", "arg": "hola"}, {"type": "valid_json"}],
    })
    assert tc.status_code == 201
    assert tc.json()["checks"][1] == {"type": "valid_json", "arg": None}
    assert client.delete(f"/test-cases/{tc.json()['id']}").status_code == 204
    assert client.get(f"/prompts/{pid}/test-cases").json() == []

    listed = client.get("/prompts").json()
    assert listed[0]["latest_version"] == 2
    assert client.get(f"/prompts/{pid}").json()["name"] == "refund-reply"


def test_domain_errors_map_to_status_codes(client):
    assert client.get("/prompts/999").status_code == 404
    client.post("/prompts", json={"name": "dup"})
    conflict = client.post("/prompts", json={"name": "dup"})
    assert conflict.status_code == 409
    assert "already exists" in conflict.json()["detail"]
    bad_check = client.post("/prompts/1/test-cases", json={
        "name": "t", "checks": [{"type": "nope"}],
    })
    assert bad_check.status_code == 422


def test_check_types_endpoint(client):
    checks = client.get("/checks").json()
    assert checks["max_length"] == "int"
    assert checks["valid_json"] is None
