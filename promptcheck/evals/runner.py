"""Creating and executing evaluation runs.

Three steps, each testable on its own:
  create_run()     validates, snapshots the version and its test cases, saves a pending run
  evaluate_case()  renders one test case, calls the LLM, scores the output (no database)
  execute_run()    runs all cases of a run concurrently in the background and saves results
"""
import asyncio
import json
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from promptcheck.db import get_connection
from promptcheck.errors import InvalidInputError, NotFoundError
from promptcheck.evals import repository as repo
from promptcheck.evals.checks import run_checks
from promptcheck.evals.gateway import PromptsGateway
from promptcheck.evals.llm_client import LLMClient
from promptcheck.evals.templates import MissingVariableError, render

INTERRUPTED = "interrupted by server restart"


@dataclass
class CaseOutcome:
    status: str                 # 'pass' | 'fail' | 'error'
    rendered_prompt: str | None
    output: str | None
    check_details: list[dict]
    error: str | None
    latency_ms: int | None
    tokens_in: int | None
    tokens_out: int | None


# ---------- 1. create ----------

def create_run(
    conn: sqlite3.Connection, gateway: PromptsGateway, version_id: int,
    provider: str, default_model: str,
) -> dict:
    version = gateway.get_version_for_run(version_id)  # NotFoundError -> 404
    test_cases = version["test_cases"]
    if not test_cases:
        raise InvalidInputError("this prompt has no active test cases to run")

    run_id = repo.insert_run(
        conn, version["prompt_id"], version["id"], version["version"], version["template"],
        version["model"] or default_model, provider, total=len(test_cases),
    )
    for tc in test_cases:
        repo.insert_pending_result(
            conn, run_id, tc["id"], tc["name"], json.dumps(tc["inputs"]), json.dumps(tc["checks"])
        )
    return get_run(conn, run_id)


# ---------- 2. evaluate one case ----------

async def evaluate_case(
    llm: LLMClient, template: str, model: str, inputs: dict, checks: list[dict]
) -> CaseOutcome:
    try:
        prompt = render(template, inputs)
    except MissingVariableError as e:
        return CaseOutcome("error", None, None, [], str(e), None, None, None)

    started = time.perf_counter()
    try:
        response = await llm.complete(prompt, model)
    except Exception as e:  # one failing call must not stop the rest of the run
        return CaseOutcome("error", prompt, None, [], f"LLM call failed: {e}", None, None, None)
    latency_ms = round((time.perf_counter() - started) * 1000)

    results = run_checks(response.text, checks)
    status = "pass" if all(r.passed for r in results) else "fail"
    return CaseOutcome(
        status, prompt, response.text, [r.to_dict() for r in results], None,
        latency_ms, response.tokens_in, response.tokens_out,
    )


# ---------- 3. execute a whole run ----------

async def execute_run(db_path: Path, run_id: int, llm: LLMClient, concurrency: int) -> None:
    """Background task: evaluate every pending result of a run, at most `concurrency` at once."""
    with closing(get_connection(db_path)) as conn:
        run = repo.get_run(conn, run_id)
        if run is None or run["status"] != "pending":
            return
        try:
            repo.mark_run_running(conn, run_id)
            conn.commit()
            semaphore = asyncio.Semaphore(concurrency)

            async def evaluate_and_save(result: sqlite3.Row) -> None:
                async with semaphore:
                    outcome = await evaluate_case(
                        llm, run["template_snapshot"], run["model"],
                        json.loads(result["inputs_snapshot"]), json.loads(result["checks_snapshot"]),
                    )
                _save_outcome(conn, result["id"], outcome)

            pending = [r for r in repo.list_results(conn, run_id) if r["status"] == "pending"]
            await asyncio.gather(*(evaluate_and_save(r) for r in pending))
            repo.finish_run(conn, run_id)
            conn.commit()
        except Exception as e:
            conn.rollback()
            repo.fail_run(conn, run_id, f"run crashed: {e}")
            conn.commit()


# ---------- 4. re-score stored outputs ----------

def rescore_run(conn: sqlite3.Connection, gateway: PromptsGateway, run_id: int) -> dict:
    """Score a completed run's stored outputs against the prompt's *current* checks.

    No LLM call: an output depends only on template + model + inputs, so a current
    test case whose inputs match a stored result can reuse that output. Outputs are
    matched by inputs, not test_case_id, because fixing a check means archiving the
    test case and adding a new one. Current test cases with no stored output are
    skipped (scoring them needs the LLM). The result is a new run; the source run
    is never changed, so old runs stay reproducible (ADR-3).
    """
    source = repo.get_run(conn, run_id)
    if source is None:
        raise NotFoundError(f"run {run_id} not found")
    if source["status"] != "completed":
        raise InvalidInputError("only a completed run can be re-scored")

    version = gateway.get_version_for_run(source["prompt_version_id"])
    stored = {
        _inputs_key(json.loads(r["inputs_snapshot"])): r
        for r in repo.list_results(conn, run_id) if r["output"] is not None
    }
    matched = [(tc, stored[_inputs_key(tc["inputs"])])
               for tc in version["test_cases"] if _inputs_key(tc["inputs"]) in stored]
    if not matched:
        raise InvalidInputError("no stored outputs match the current test cases")

    new_id = repo.insert_run(
        conn, source["prompt_id"], source["prompt_version_id"], source["version"],
        source["template_snapshot"], source["model"], "rescore", total=len(matched),
    )
    repo.mark_run_running(conn, new_id)
    for tc, old in matched:
        result_id = repo.insert_pending_result(
            conn, new_id, tc["id"], tc["name"], json.dumps(tc["inputs"]), json.dumps(tc["checks"])
        )
        results = run_checks(old["output"], tc["checks"])
        repo.update_result(conn, result_id, {
            "status": "pass" if all(r.passed for r in results) else "fail",
            "rendered_prompt": old["rendered_prompt"],
            "output": old["output"],
            "check_details": json.dumps([r.to_dict() for r in results]),
            "latency_ms": old["latency_ms"],
            "tokens_in": old["tokens_in"],
            "tokens_out": old["tokens_out"],
        })
    repo.finish_run(conn, new_id)
    return get_run(conn, new_id, with_results=True)


def _inputs_key(inputs: dict) -> str:
    return json.dumps(inputs, sort_keys=True)


def _save_outcome(conn: sqlite3.Connection, result_id: int, outcome: CaseOutcome) -> None:
    repo.update_result(conn, result_id, {
        "status": outcome.status,
        "rendered_prompt": outcome.rendered_prompt,
        "output": outcome.output,
        "check_details": json.dumps(outcome.check_details),
        "error": outcome.error,
        "latency_ms": outcome.latency_ms,
        "tokens_in": outcome.tokens_in,
        "tokens_out": outcome.tokens_out,
    })
    conn.commit()  # commit each result so the dashboard can show progress


# ---------- reading ----------

def get_run(conn: sqlite3.Connection, run_id: int, with_results: bool = False) -> dict:
    row = repo.get_run(conn, run_id)
    if row is None:
        raise NotFoundError(f"run {run_id} not found")
    run = _run_to_dict(row)
    if with_results:
        run["results"] = [_result_to_dict(r) for r in repo.list_results(conn, run_id)]
    return run


def list_runs(conn: sqlite3.Connection, prompt_id: int | None = None) -> list[dict]:
    return [_run_to_dict(row) for row in repo.list_runs(conn, prompt_id)]


def recover_interrupted_runs(conn: sqlite3.Connection) -> int:
    """Called at startup: background tasks die with the process, so any run still
    pending/running from before a restart can never finish. Mark it failed."""
    count = repo.fail_unfinished_runs(conn, INTERRUPTED)
    conn.commit()
    return count


def _run_to_dict(row: sqlite3.Row) -> dict:
    run = dict(row)
    # only a completed run has a meaningful pass rate; 0.0 on a pending run would look like "all failed"
    finished = run["status"] == "completed" and run["total"]
    run["pass_rate"] = round(run["passed"] / run["total"], 4) if finished else None
    return run


def _result_to_dict(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["inputs"] = json.loads(result.pop("inputs_snapshot"))
    result["checks"] = json.loads(result.pop("checks_snapshot"))
    result["check_details"] = json.loads(result["check_details"]) if result["check_details"] else []
    return result
