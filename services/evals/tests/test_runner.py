import asyncio

import pytest

from app import repository as repo
from app import runner
from app.errors import InvalidInputError, NotFoundError
from app.llm_client import FakeLLMClient, LLMResponse


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


class StubJudge:
    def __init__(self, verdict):
        self.verdict = verdict

    async def judge(self, output, rubric):
        return self.verdict, f"stub says {self.verdict}"


class BrokenJudge:
    async def judge(self, output, rubric):
        raise TimeoutError("judge timed out")


@pytest.fixture
def version(conn, gateway):
    """A prompt with one version and three test cases: one passes, one fails, one errors."""
    p = gateway.create_prompt("refund-reply")
    v = gateway.publish_version(p["id"], "Responde con un reembolso a: {message}")
    gateway.add_test_case(p["id"], "passes", {"message": "hola"},
                          [{"type": "contains", "arg": "reembolso"}])
    gateway.add_test_case(p["id"], "fails", {"message": "hola"},
                          [{"type": "valid_json"}])
    gateway.add_test_case(p["id"], "errors", {"wrong_var": "x"},
                          [{"type": "contains", "arg": "x"}])
    return v


def make_run(conn, settings, gateway, version):
    run = runner.create_run(conn, gateway, version["id"],
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


def test_evaluate_case_uses_the_judge_for_judge_checks():
    checks = [{"type": "contains", "arg": "Hola"}, {"type": "llm_judge", "arg": "is friendly"}]
    outcome = asyncio.run(runner.evaluate_case(
        FakeLLMClient(), "Hola {name}", "m", {"name": "Ana"}, checks, judge=StubJudge(False)))
    assert outcome.status == "fail"
    assert [d["type"] for d in outcome.check_details] == ["contains", "llm_judge"]
    assert outcome.check_details[1] == {"type": "llm_judge", "passed": False, "detail": "stub says False"}


def test_evaluate_case_judge_failure_is_an_error_but_keeps_the_output():
    checks = [{"type": "llm_judge", "arg": "is friendly"}]
    outcome = asyncio.run(runner.evaluate_case(
        FakeLLMClient(), "Hola", "m", {}, checks, judge=BrokenJudge()))
    assert outcome.status == "error"
    assert outcome.output == "Hola"
    assert outcome.error == "judge call failed: judge timed out"


def test_evaluate_case_llm_failure_is_an_error():
    outcome = asyncio.run(runner.evaluate_case(FailingLLM(), "Hi", "m", {}, []))
    assert outcome.status == "error"
    assert outcome.error == "LLM call failed: provider timed out"
    assert outcome.rendered_prompt == "Hi"


# ---------- create_run ----------

def test_create_run_snapshots_version_and_test_cases(conn, settings, gateway, version):
    run = make_run(conn, settings, gateway, version)
    assert run["status"] == "pending"
    assert (run["total"], run["version"], run["model"]) == (3, 1, "default-model")
    assert run["template_snapshot"] == "Responde con un reembolso a: {message}"
    assert run["pass_rate"] is None

    # editing the prompt afterwards must not change what the run tests
    gateway.publish_version(version["prompt_id"], "Something else: {message}")
    results = runner.get_run(conn, run["id"], with_results=True)["results"]
    assert [r["test_case_name"] for r in results] == ["passes", "fails", "errors"]
    assert all(r["status"] == "pending" for r in results)


def test_create_run_uses_version_model_when_set(conn, settings, gateway):
    p = gateway.create_prompt("p")
    v = gateway.publish_version(p["id"], "Hi", model="claude-sonnet-5")
    gateway.add_test_case(p["id"], "t", {}, [{"type": "valid_json"}])
    assert make_run(conn, settings, gateway, v)["model"] == "claude-sonnet-5"


def test_create_run_without_test_cases_is_rejected(conn, settings, gateway):
    p = gateway.create_prompt("empty")
    v = gateway.publish_version(p["id"], "Hi")
    with pytest.raises(InvalidInputError, match="no active test cases"):
        make_run(conn, settings, gateway, v)


def test_create_run_for_missing_version(conn, settings, gateway):
    with pytest.raises(NotFoundError):
        runner.create_run(conn, gateway, 999, "fake", "m")


# ---------- execute_run ----------

def test_execute_run_scores_every_case(conn, settings, gateway, version):
    run = make_run(conn, settings, gateway, version)
    asyncio.run(runner.execute_run(settings.database_url, run["id"], FakeLLMClient(), concurrency=2))

    done = runner.get_run(conn, run["id"], with_results=True)
    assert done["status"] == "completed"
    assert (done["passed"], done["failed"], done["errored"]) == (1, 1, 1)
    assert done["pass_rate"] == round(1 / 3, 4)
    assert done["started_at"] and done["finished_at"]
    assert [r["status"] for r in done["results"]] == ["pass", "fail", "error"]


def test_execute_run_respects_concurrency_limit(conn, settings, gateway):
    p = gateway.create_prompt("many")
    v = gateway.publish_version(p["id"], "Hi")
    for i in range(8):
        gateway.add_test_case(p["id"], f"t{i}", {}, [{"type": "contains", "arg": "Hi"}])
    run = make_run(conn, settings, gateway, v)

    llm = ConcurrencyTrackingLLM()
    asyncio.run(runner.execute_run(settings.database_url, run["id"], llm, concurrency=3))
    assert llm.max_active == 3
    assert runner.get_run(conn, run["id"])["passed"] == 8


def test_execute_run_ignores_missing_or_already_started_runs(conn, settings, gateway, version):
    asyncio.run(runner.execute_run(settings.database_url, 999, FakeLLMClient(), 1))  # no crash
    run = make_run(conn, settings, gateway, version)
    asyncio.run(runner.execute_run(settings.database_url, run["id"], FakeLLMClient(), 1))
    first_finish = runner.get_run(conn, run["id"])["finished_at"]
    asyncio.run(runner.execute_run(settings.database_url, run["id"], FakeLLMClient(), 1))
    assert runner.get_run(conn, run["id"])["finished_at"] == first_finish  # not re-run


def test_execute_run_marks_run_failed_if_it_crashes(conn, settings, gateway, version, monkeypatch):
    run = make_run(conn, settings, gateway, version)

    def broken_update(*args):
        raise RuntimeError("disk full")
    monkeypatch.setattr(repo, "update_result", broken_update)

    asyncio.run(runner.execute_run(settings.database_url, run["id"], FakeLLMClient(), 2))
    failed = runner.get_run(conn, run["id"])
    assert failed["status"] == "failed"
    assert failed["error"] == "run crashed: disk full"


# ---------- reading and recovery ----------

def test_list_runs_filters_by_prompt(conn, settings, gateway, version):
    run = make_run(conn, settings, gateway, version)
    assert [r["id"] for r in runner.list_runs(conn)] == [run["id"]]
    assert [r["id"] for r in runner.list_runs(conn, version["prompt_id"])] == [run["id"]]
    assert runner.list_runs(conn, 999) == []


def test_get_missing_run(conn):
    with pytest.raises(NotFoundError):
        runner.get_run(conn, 999)


def test_recover_interrupted_runs(conn, settings, gateway, version):
    stuck = make_run(conn, settings, gateway, version)
    assert runner.recover_interrupted_runs(conn) == 1

    recovered = runner.get_run(conn, stuck["id"], with_results=True)
    assert recovered["status"] == "failed"
    assert recovered["error"] == runner.INTERRUPTED
    assert all(r["status"] == "error" for r in recovered["results"])
    assert runner.recover_interrupted_runs(conn) == 0  # finished runs are left alone


# ---------- rescore_run ----------

def completed_run(conn, settings, gateway, version):
    run = make_run(conn, settings, gateway, version)
    asyncio.run(runner.execute_run(settings.database_url, run["id"], FakeLLMClient(), 2))
    return run


def test_rescore_applies_current_checks_to_stored_outputs(conn, settings, gateway, version):
    run = completed_run(conn, settings, gateway, version)
    cases = {tc["name"]: tc for tc in gateway.list_test_cases(version["prompt_id"])}
    # "fixing" a check = archive the test case and re-add it with the same inputs
    gateway.archive_test_case(cases["passes"]["id"])
    gateway.add_test_case(version["prompt_id"], "passes v2", {"message": "hola"},
                          [{"type": "contains", "arg": "tienda"}])
    conn.commit()

    new = asyncio.run(runner.rescore_run(conn, gateway, run["id"]))

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


def test_rescore_runs_judge_checks(conn, settings, gateway, version):
    run = completed_run(conn, settings, gateway, version)
    cases = {tc["name"]: tc for tc in gateway.list_test_cases(version["prompt_id"])}
    gateway.archive_test_case(cases["passes"]["id"])
    gateway.add_test_case(version["prompt_id"], "judged", {"message": "hola"},
                          [{"type": "llm_judge", "arg": "offers a refund"}])
    conn.commit()

    new = asyncio.run(runner.rescore_run(
        conn, gateway, run["id"], judge=StubJudge(True)))
    judged = next(r for r in new["results"] if r["test_case_name"] == "judged")
    assert judged["status"] == "pass"


def test_rescore_marks_a_failed_judge_call_as_an_error(conn, settings, gateway, version):
    run = completed_run(conn, settings, gateway, version)
    gateway.add_test_case(version["prompt_id"], "judged", {"message": "hola"},
                          [{"type": "llm_judge", "arg": "offers a refund"}])
    conn.commit()

    new = asyncio.run(runner.rescore_run(
        conn, gateway, run["id"], judge=BrokenJudge()))
    judged = next(r for r in new["results"] if r["test_case_name"] == "judged")
    assert judged["status"] == "error"
    assert "judge call failed" in judged["error"]


def test_rescore_requires_a_completed_run(conn, settings, gateway, version):
    run = make_run(conn, settings, gateway, version)  # still pending
    with pytest.raises(InvalidInputError):
        asyncio.run(runner.rescore_run(conn, gateway, run["id"]))


def test_rescore_missing_run(conn, settings, gateway):
    with pytest.raises(NotFoundError):
        asyncio.run(runner.rescore_run(conn, gateway, 999))


def test_rescore_with_no_matching_inputs(conn, settings, gateway, version):
    run = completed_run(conn, settings, gateway, version)
    for tc in gateway.list_test_cases(version["prompt_id"]):
        gateway.archive_test_case(tc["id"])
    gateway.add_test_case(version["prompt_id"], "new input", {"message": "adiós"},
                          [{"type": "contains", "arg": "adiós"}])
    with pytest.raises(InvalidInputError):
        asyncio.run(runner.rescore_run(conn, gateway, run["id"]))
