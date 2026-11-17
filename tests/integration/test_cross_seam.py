"""Cross-seam integration test, run against the real compose stack (ADR-9).

The two services can't be imported into one process (both packages are named `app`),
and a stub of prompts would only prove that evals agrees with the stub. So this test
starts nothing itself: it calls the running services over HTTP, the way the UI does.

    docker compose up -d --build
    pip install -r tests/integration/requirements.txt
    pytest tests/integration

PROMPTS_URL and EVALS_URL default to the ports compose publishes. The partial-failure
test stops and restarts the prompts container, so it needs the docker CLI.
"""
import os
import shutil
import subprocess
import time
import uuid

import httpx
import pytest

PROMPTS_URL = os.environ.get("PROMPTS_URL", "http://localhost:8001")
EVALS_URL = os.environ.get("EVALS_URL", "http://localhost:8002")


@pytest.fixture(scope="module")
def prompts():
    with httpx.Client(base_url=PROMPTS_URL, timeout=10) as client:
        yield client


@pytest.fixture(scope="module")
def evals():
    with httpx.Client(base_url=EVALS_URL, timeout=10) as client:
        yield client


@pytest.fixture
def prompt_version(prompts):
    """A fresh prompt with one version and one test case, created in the prompts service."""
    name = f"it-{uuid.uuid4().hex[:8]}"  # unique, so the test can run again on the same database
    prompt = prompts.post("/prompts", json={"name": name, "description": "integration test"})
    assert prompt.status_code == 201, prompt.text
    prompt_id = prompt.json()["id"]

    version = prompts.post(f"/prompts/{prompt_id}/versions", json={"template": "Say hello to {person}."})
    assert version.status_code == 201, version.text

    case = prompts.post(f"/prompts/{prompt_id}/test-cases", json={
        "name": "greets the person",
        "inputs": {"person": "Ada"},
        "checks": [{"type": "contains", "arg": "Ada"}],
    })
    assert case.status_code == 201, case.text
    return version.json()


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


@pytest.fixture
def prompts_stopped():
    if not shutil.which("docker"):
        pytest.skip("needs the docker CLI to stop the prompts container")
    subprocess.run(["docker", "compose", "stop", "prompts"], check=True, capture_output=True)
    try:
        yield
    finally:
        subprocess.run(["docker", "compose", "start", "prompts"], check=True, capture_output=True)
        wait_until_healthy(PROMPTS_URL)


def wait_until_healthy(url: str, timeout_s: float = 90) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/health", timeout=3).status_code == 200:
                return
        except httpx.TransportError:
            pass
        time.sleep(1)
    pytest.fail(f"{url} did not become healthy within {timeout_s}s")


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
