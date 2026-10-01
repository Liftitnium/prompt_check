"""HTTP-level tests for evals: the 202 + background flow and error mapping."""


def setup_prompt(client):
    pid = client.post("/prompts", json={"name": "refund-reply"}).json()["id"]
    version = client.post(f"/prompts/{pid}/versions",
                          json={"template": "Reembolso para: {message}"}).json()
    client.post(f"/prompts/{pid}/test-cases", json={
        "name": "mentions refund", "inputs": {"message": "hola"},
        "checks": [{"type": "contains", "arg": "reembolso"}],
    })
    return pid, version["id"]


def test_run_is_accepted_then_completes_in_background(client):
    pid, version_id = setup_prompt(client)

    started = client.post("/runs", json={"prompt_version_id": version_id})
    assert started.status_code == 202
    assert started.json()["status"] == "pending"

    # TestClient runs background tasks before returning, so the run is finished here
    run = client.get(f"/runs/{started.json()['id']}").json()
    assert run["status"] == "completed"
    assert run["pass_rate"] == 1.0
    assert run["results"][0]["output"] == "Reembolso para: hola"
    assert run["results"][0]["check_details"][0]["passed"] is True

    assert len(client.get("/runs", params={"prompt_id": pid}).json()) == 1


def test_run_errors_map_to_status_codes(client):
    assert client.post("/runs", json={"prompt_version_id": 999}).status_code == 404
    assert client.get("/runs/999").status_code == 404

    pid = client.post("/prompts", json={"name": "no-tests"}).json()["id"]
    vid = client.post(f"/prompts/{pid}/versions", json={"template": "Hi"}).json()["id"]
    assert client.post("/runs", json={"prompt_version_id": vid}).status_code == 422
