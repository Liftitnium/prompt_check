"""Fixtures shared by the integration tests, which run against the real compose stack.

PROMPTS_URL, EVALS_URL and UI_URL default to the ports compose publishes. Stopping a
service (the partial-failure tests) needs the docker CLI.
"""
import os
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager

import httpx
import pytest

PROMPTS_URL = os.environ.get("PROMPTS_URL", "http://localhost:8001")
EVALS_URL = os.environ.get("EVALS_URL", "http://localhost:8002")
UI_URL = os.environ.get("UI_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def prompts():
    with httpx.Client(base_url=PROMPTS_URL, timeout=10) as client:
        yield client


@pytest.fixture(scope="session")
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
    return {**version.json(), "prompt_name": name}


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


@contextmanager
def prompts_down():
    """Stop the prompts container for the duration of the block, then wait for it to come back."""
    if not shutil.which("docker"):
        pytest.skip("needs the docker CLI to stop the prompts container")
    subprocess.run(["docker", "compose", "stop", "prompts"], check=True, capture_output=True)
    try:
        yield
    finally:
        subprocess.run(["docker", "compose", "start", "prompts"], check=True, capture_output=True)
        wait_until_healthy(PROMPTS_URL)


@pytest.fixture
def prompts_stopped():
    with prompts_down():
        yield
