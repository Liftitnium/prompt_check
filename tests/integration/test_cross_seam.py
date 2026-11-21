"""Cross-seam integration test, run against the real compose stack (ADR-9).

The two services can't be imported into one process (both packages are named `app`),
and a stub of prompts would only prove that evals agrees with the stub. So this test
starts nothing itself: it calls the running services over HTTP, the way the UI does.

    docker compose up -d --build
    pip install -r tests/integration/requirements.txt
    pytest tests/integration

Fixtures (the HTTP clients, a fresh prompt version, stopping prompts) are in conftest.py.
"""
import time

import pytest


def wait_for_run(evals, run_id: int, timeout_s: float = 30) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        run = evals.get(f"/runs/{run_id}").json()
        if run["status"] in ("completed", "failed"):
            return run
        time.sleep(0.5)
    pytest.fail(f"run {run_id} did not finish within {timeout_s}s")


def test_a_run_in_evals_uses_the_version_and_test_cases_stored_in_prompts(prompts, evals, prompt_version):
    started = evals.post("/runs", json={"prompt_version_id": prompt_version["id"]})
    assert started.status_code == 202, started.text

    run = wait_for_run(evals, started.json()["id"])

    # everything below came across the seam from GET /versions/{id}/for-run
    assert run["status"] == "completed"
    assert run["prompt_id"] == prompt_version["prompt_id"]
    assert run["version"] == prompt_version["version"]
    assert run["template_snapshot"] == "Say hello to {person}."
    [result] = run["results"]
    assert result["test_case_name"] == "greets the person"
    # the fake LLM echoes the prompt, so the input from prompts was rendered into the template
    assert result["rendered_prompt"] == "Say hello to Ada."
    assert result["status"] == "pass"


def test_a_version_missing_in_prompts_is_a_404_from_evals(evals):
    response = evals.post("/runs", json={"prompt_version_id": 999_999_999})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_with_prompts_down_evals_keeps_serving_and_the_cross_seam_flow_fails_cleanly(
    evals, prompt_version, prompts_stopped
):
    # evals' own domain still works: health reports only its own database
    assert evals.get("/health").status_code == 200
    assert evals.get("/runs").status_code == 200

    # the flow that needs prompts fails fast with a clear message, not a hang or a stack trace
    started = time.monotonic()
    response = evals.post("/runs", json={"prompt_version_id": prompt_version["id"]})
    elapsed = time.monotonic() - started

    assert response.status_code == 503
    assert "prompts service" in response.json()["detail"]
    assert elapsed < 5, f"took {elapsed:.1f}s; PROMPTS_TIMEOUT_S is 2"
