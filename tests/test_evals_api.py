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


def test_compare_two_versions_over_http(client):
    pid, v1 = setup_prompt(client)  # v1 template mentions "Reembolso", so the check passes
    v2 = client.post(f"/prompts/{pid}/versions",
                     json={"template": "Gracias por escribir: {message}"}).json()["id"]
    run1 = client.post("/runs", json={"prompt_version_id": v1}).json()["id"]
    run2 = client.post("/runs", json={"prompt_version_id": v2}).json()["id"]

    report = client.get("/runs/compare", params={"base": run1, "candidate": run2}).json()
    assert report["verdict"] == "block"
    assert report["summary"]["regressed"] == 1
    assert report["cases"]["regressed"][0]["candidate_failed_checks"] == ["missing 'reembolso'"]
    assert report["metrics"]["pass_rate"] == {"base": 1.0, "candidate": 0.0, "change": -1.0}

    assert client.get("/runs/compare", params={"base": run1, "candidate": 999}).status_code == 404
