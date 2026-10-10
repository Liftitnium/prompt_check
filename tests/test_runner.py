import asyncio

import pytest

from promptcheck.errors import InvalidInputError, NotFoundError
from promptcheck.evals import repository as repo
from promptcheck.evals import runner
from promptcheck.evals.gateway import InProcessPromptsGateway
from promptcheck.evals.llm_client import FakeLLMClient, LLMResponse
from promptcheck.prompts import service as prompts


class FailingLLM:
    name = "failing"

    async def complete(self, prompt, model):
        raise TimeoutError("provider timed out")


class ConcurrencyTrackingLLM:
    """Records how many calls were in flight at once."""
    name = "tracking"

    def __init__(self):
        self.active = 0
        self.max_active = 0

    async def complete(self, prompt, model):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return LLMResponse(prompt, 1, 1)


@pytest.fixture
def version(conn):
    """A prompt with one version and three test cases: one passes, one fails, one errors."""
    p = prompts.create_prompt(conn, "refund-reply")
    v = prompts.publish_version(conn, p["id"], "Responde con un reembolso a: {message}")
    prompts.add_test_case(conn, p["id"], "passes", {"message": "hola"},
                          [{"type": "contains", "arg": "reembolso"}])
    prompts.add_test_case(conn, p["id"], "fails", {"message": "hola"},
                          [{"type": "valid_json"}])
    prompts.add_test_case(conn, p["id"], "errors", {"wrong_var": "x"},
                          [{"type": "contains", "arg": "x"}])
    conn.commit()
    return v


def make_run(conn, settings, version):
    run = runner.create_run(conn, InProcessPromptsGateway(settings.db_path), version["id"],
                            provider="fake", default_model="default-model")
    conn.commit()
    return run


# ---------- evaluate_case (no database) ----------

def test_evaluate_case_pass():
    outcome = asyncio.run(runner.evaluate_case(
        FakeLLMClient(), "Hola {name}", "m", {"name": "Ana"}, [{"type": "contains", "arg": "Ana"}]))
    assert outcome.status == "pass"
    assert outcome.output == "Hola Ana"
    assert outcome.check_details == [{"type": "contains", "passed": True, "detail": "found 'Ana'"}]
    assert outcome.latency_ms is not None and outcome.tokens_in == 2


def test_evaluate_case_fails_if_any_check_fails():
    outcome = asyncio.run(runner.evaluate_case(
        FakeLLMClient(), "Hola", "m", {},
        [{"type": "contains", "arg": "Hola"}, {"type": "valid_json"}]))
    assert outcome.status == "fail"
    assert [c["passed"] for c in outcome.check_details] == [True, False]


def test_evaluate_case_missing_variable_is_an_error():
    outcome = asyncio.run(runner.evaluate_case(FakeLLMClient(), "Hi {name}", "m", {}, []))
    assert outcome.status == "error"
    assert "name" in outcome.error
    assert outcome.rendered_prompt is None


def test_evaluate_case_llm_failure_is_an_error():
    outcome = asyncio.run(runner.evaluate_case(FailingLLM(), "Hi", "m", {}, []))
    assert outcome.status == "error"
    assert outcome.error == "LLM call failed: provider timed out"
    assert outcome.rendered_prompt == "Hi"


# ---------- create_run ----------

def test_create_run_snapshots_version_and_test_cases(conn, settings, version):
    run = make_run(conn, settings, version)
    assert run["status"] == "pending"
    assert (run["total"], run["version"], run["model"]) == (3, 1, "default-model")
    assert run["template_snapshot"] == "Responde con un reembolso a: {message}"
    assert run["pass_rate"] is None

    # editing the prompt afterwards must not change what the run tests
    prompts.publish_version(conn, version["prompt_id"], "Something else: {message}")
    results = runner.get_run(conn, run["id"], with_results=True)["results"]
    assert [r["test_case_name"] for r in results] == ["passes", "fails", "errors"]
    assert all(r["status"] == "pending" for r in results)


def test_create_run_uses_version_model_when_set(conn, settings):
    p = prompts.create_prompt(conn, "p")
    v = prompts.publish_version(conn, p["id"], "Hi", model="claude-sonnet-5")
    prompts.add_test_case(conn, p["id"], "t", {}, [{"type": "valid_json"}])
    conn.commit()
    assert make_run(conn, settings, v)["model"] == "claude-sonnet-5"


def test_create_run_without_test_cases_is_rejected(conn, settings):
    p = prompts.create_prompt(conn, "empty")
    v = prompts.publish_version(conn, p["id"], "Hi")
    conn.commit()
    with pytest.raises(InvalidInputError, match="no active test cases"):
        make_run(conn, settings, v)


def test_create_run_for_missing_version(conn, settings):
    with pytest.raises(NotFoundError):
        runner.create_run(conn, InProcessPromptsGateway(settings.db_path), 999, "fake", "m")


# ---------- execute_run ----------

def test_execute_run_scores_every_case(conn, settings, version):
    run = make_run(conn, settings, version)
    asyncio.run(runner.execute_run(settings.db_path, run["id"], FakeLLMClient(), concurrency=2))

    done = runner.get_run(conn, run["id"], with_results=True)
    assert done["status"] == "completed"
    assert (done["passed"], done["failed"], done["errored"]) == (1, 1, 1)
    assert done["pass_rate"] == round(1 / 3, 4)
    assert done["started_at"] and done["finished_at"]
    assert [r["status"] for r in done["results"]] == ["pass", "fail", "error"]


def test_execute_run_respects_concurrency_limit(conn, settings):
    p = prompts.create_prompt(conn, "many")
    v = prompts.publish_version(conn, p["id"], "Hi")
    for i in range(8):
        prompts.add_test_case(conn, p["id"], f"t{i}", {}, [{"type": "contains", "arg": "Hi"}])
    conn.commit()
    run = make_run(conn, settings, v)

    llm = ConcurrencyTrackingLLM()
    asyncio.run(runner.execute_run(settings.db_path, run["id"], llm, concurrency=3))
    assert llm.max_active == 3
    assert runner.get_run(conn, run["id"])["passed"] == 8


def test_execute_run_ignores_missing_or_already_started_runs(conn, settings, version):
    asyncio.run(runner.execute_run(settings.db_path, 999, FakeLLMClient(), 1))  # no crash
    run = make_run(conn, settings, version)
    asyncio.run(runner.execute_run(settings.db_path, run["id"], FakeLLMClient(), 1))
    first_finish = runner.get_run(conn, run["id"])["finished_at"]
    asyncio.run(runner.execute_run(settings.db_path, run["id"], FakeLLMClient(), 1))
    assert runner.get_run(conn, run["id"])["finished_at"] == first_finish  # not re-run


def test_execute_run_marks_run_failed_if_it_crashes(conn, settings, version, monkeypatch):
    run = make_run(conn, settings, version)

    def broken_update(*args):
        raise RuntimeError("disk full")
    monkeypatch.setattr(repo, "update_result", broken_update)

    asyncio.run(runner.execute_run(settings.db_path, run["id"], FakeLLMClient(), 2))
    failed = runner.get_run(conn, run["id"])
    assert failed["status"] == "failed"
    assert failed["error"] == "run crashed: disk full"


# ---------- reading and recovery ----------

def test_list_runs_filters_by_prompt(conn, settings, version):
    run = make_run(conn, settings, version)
    assert [r["id"] for r in runner.list_runs(conn)] == [run["id"]]
    assert [r["id"] for r in runner.list_runs(conn, version["prompt_id"])] == [run["id"]]
    assert runner.list_runs(conn, 999) == []


def test_get_missing_run(conn):
    with pytest.raises(NotFoundError):
        runner.get_run(conn, 999)


def test_recover_interrupted_runs(conn, settings, version):
    stuck = make_run(conn, settings, version)
    assert runner.recover_interrupted_runs(conn) == 1

    recovered = runner.get_run(conn, stuck["id"], with_results=True)
    assert recovered["status"] == "failed"
    assert recovered["error"] == runner.INTERRUPTED
    assert all(r["status"] == "error" for r in recovered["results"])
    assert runner.recover_interrupted_runs(conn) == 0  # finished runs are left alone


# ---------- rescore_run ----------

def completed_run(conn, settings, version):
    run = make_run(conn, settings, version)
    asyncio.run(runner.execute_run(settings.db_path, run["id"], FakeLLMClient(), 2))
    return run


def test_rescore_applies_current_checks_to_stored_outputs(conn, settings, version):
    run = completed_run(conn, settings, version)
    cases = {tc["name"]: tc for tc in prompts.list_test_cases(conn, version["prompt_id"])}
    # "fixing" a check = archive the test case and re-add it with the same inputs
    prompts.archive_test_case(conn, cases["passes"]["id"])
    prompts.add_test_case(conn, version["prompt_id"], "passes v2", {"message": "hola"},
                          [{"type": "contains", "arg": "tienda"}])
    conn.commit()

    new = runner.rescore_run(conn, InProcessPromptsGateway(settings.db_path), run["id"])

    assert new["id"] != run["id"]
    assert new["provider"] == "rescore"
    assert new["status"] == "completed"
    by_name = {r["test_case_name"]: r for r in new["results"]}
    # "errors" had no stored output, so it needs the LLM and is skipped
    assert set(by_name) == {"fails", "passes v2"}
    assert by_name["passes v2"]["status"] == "fail"
    assert by_name["passes v2"]["output"] == "Responde con un reembolso a: hola"
    assert (new["total"], new["passed"], new["failed"]) == (2, 0, 2)

    source = runner.get_run(conn, run["id"], with_results=True)
    assert [r["status"] for r in source["results"]] == ["pass", "fail", "error"]


def test_rescore_requires_a_completed_run(conn, settings, version):
    run = make_run(conn, settings, version)  # still pending
    with pytest.raises(InvalidInputError):
        runner.rescore_run(conn, InProcessPromptsGateway(settings.db_path), run["id"])


def test_rescore_missing_run(conn, settings):
    with pytest.raises(NotFoundError):
        runner.rescore_run(conn, InProcessPromptsGateway(settings.db_path), 999)


def test_rescore_with_no_matching_inputs(conn, settings, version):
    run = completed_run(conn, settings, version)
    for tc in prompts.list_test_cases(conn, version["prompt_id"]):
        prompts.archive_test_case(conn, tc["id"])
    prompts.add_test_case(conn, version["prompt_id"], "new input", {"message": "adiós"},
                          [{"type": "contains", "arg": "adiós"}])
    conn.commit()
    with pytest.raises(InvalidInputError):
        runner.rescore_run(conn, InProcessPromptsGateway(settings.db_path), run["id"])
