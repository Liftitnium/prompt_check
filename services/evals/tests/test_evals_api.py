"""HTTP-level tests for evals: the 202 + background flow, error mapping, partial failure."""


def setup_prompt(gateway):
    pid = gateway.create_prompt("refund-reply")["id"]
    version = gateway.publish_version(pid, "Reembolso para: {message}")
    gateway.add_test_case(pid, "mentions refund", {"message": "hola"},
                          [{"type": "contains", "arg": "reembolso"}])
    return pid, version["id"]


def test_run_is_accepted_then_completes_in_background(client, gateway):
    pid, version_id = setup_prompt(gateway)

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


def test_run_errors_map_to_status_codes(client, gateway):
    assert client.post("/runs", json={"prompt_version_id": 999}).status_code == 404
    assert client.get("/runs/999").status_code == 404

    pid = gateway.create_prompt("no-tests")["id"]
    vid = gateway.publish_version(pid, "Hi")["id"]
    assert client.post("/runs", json={"prompt_version_id": vid}).status_code == 422


def test_compare_two_versions_over_http(client, gateway):
    pid, v1 = setup_prompt(gateway)  # v1 template mentions "Reembolso", so the check passes
    v2 = gateway.publish_version(pid, "Gracias por escribir: {message}")["id"]
    run1 = client.post("/runs", json={"prompt_version_id": v1}).json()["id"]
    run2 = client.post("/runs", json={"prompt_version_id": v2}).json()["id"]

    report = client.get("/runs/compare", params={"base": run1, "candidate": run2}).json()
    assert report["verdict"] == "block"
    assert report["summary"]["regressed"] == 1
    assert report["cases"]["regressed"][0]["candidate_failed_checks"] == ["missing 'reembolso'"]
    assert report["metrics"]["pass_rate"] == {"base": 1.0, "candidate": 0.0, "change": -1.0}

    assert client.get("/runs/compare", params={"base": run1, "candidate": 999}).status_code == 404


def test_rescore_creates_a_comparable_run(client, gateway):
    pid, version_id = setup_prompt(gateway)
    run_id = client.post("/runs", json={"prompt_version_id": version_id}).json()["id"]

    resp = client.post(f"/runs/{run_id}/rescore")
    assert resp.status_code == 201
    new = resp.json()
    assert new["provider"] == "rescore"
    assert new["pass_rate"] == 1.0

    report = client.get("/runs/compare", params={"base": run_id, "candidate": new["id"]}).json()
    assert report["verdict"] == "ship"
    assert client.post("/runs/999/rescore").status_code == 404


def test_prompts_outage_only_blocks_new_runs(client, gateway):
    """Designed partial failure: with prompts down, starting a run is a clear 503,
    but everything already stored can still be read and compared."""
    _, version_id = setup_prompt(gateway)
    run_id = client.post("/runs", json={"prompt_version_id": version_id}).json()["id"]

    gateway.down = True
    blocked = client.post("/runs", json={"prompt_version_id": version_id})
    assert blocked.status_code == 503
    assert "prompts service" in blocked.json()["detail"]
    assert client.post(f"/runs/{run_id}/rescore").status_code == 503

    assert client.get("/runs").status_code == 200
    assert client.get(f"/runs/{run_id}").json()["status"] == "completed"
    assert client.get("/runs/compare", params={"base": run_id, "candidate": run_id}).status_code == 200
    assert client.get("/health").json()["status"] == "ok"
