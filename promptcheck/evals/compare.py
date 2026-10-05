"""Compare two completed runs of the same prompt: what regressed, what got fixed,
and should the candidate ship? Pure functions over run dicts; no database."""
import math

from promptcheck.errors import InvalidInputError


def compare_runs(base: dict, candidate: dict) -> dict:
    """base/candidate are runs with results, as returned by runner.get_run(..., with_results=True)."""
    _check_comparable(base, candidate)
    base_by_case = {r["test_case_id"]: r for r in base["results"]}
    cand_by_case = {r["test_case_id"]: r for r in candidate["results"]}

    cases = {name: [] for name in
             ("regressed", "fixed", "still_passing", "still_failing", "new", "removed")}
    for case_id in sorted(base_by_case.keys() | cand_by_case.keys()):
        before, after = base_by_case.get(case_id), cand_by_case.get(case_id)
        cases[_categorize(before, after)].append(_case_summary(before, after))

    regressions = len(cases["regressed"])
    pass_rate_delta = round(candidate["pass_rate"] - base["pass_rate"], 4)
    return {
        "base_run_id": base["id"],
        "candidate_run_id": candidate["id"],
        "base_version": base["version"],
        "candidate_version": candidate["version"],
        "verdict": "ship" if regressions == 0 and pass_rate_delta >= 0 else "block",
        "summary": {name: len(items) for name, items in cases.items()},
        "metrics": {
            "pass_rate": _delta(base["pass_rate"], candidate["pass_rate"]),
            "avg_latency_ms": _delta(*(_avg(_latencies(run)) for run in (base, candidate))),
            "p95_latency_ms": _delta(*(p95(_latencies(run)) for run in (base, candidate))),
            "total_tokens": _delta(_tokens(base), _tokens(candidate)),
        },
        "cases": cases,
    }


def _check_comparable(base: dict, candidate: dict) -> None:
    if base["prompt_id"] != candidate["prompt_id"]:
        raise InvalidInputError("can only compare runs of the same prompt")
    for run in (base, candidate):
        if run["status"] != "completed":
            raise InvalidInputError(f"run {run['id']} is {run['status']}, not completed")


def _categorize(before: dict | None, after: dict | None) -> str:
    if before is None:
        return "new"
    if after is None:
        return "removed"
    passed_before, passed_after = before["status"] == "pass", after["status"] == "pass"
    if passed_before and not passed_after:
        return "regressed"
    if not passed_before and passed_after:
        return "fixed"
    return "still_passing" if passed_after else "still_failing"


def _case_summary(before: dict | None, after: dict | None) -> dict:
    either = after or before
    return {
        "test_case_id": either["test_case_id"],
        "test_case_name": either["test_case_name"],
        "base_status": before["status"] if before else None,
        "candidate_status": after["status"] if after else None,
        # the failing checks explain *why* a case regressed
        "candidate_failed_checks": [
            c["detail"] for c in (after["check_details"] if after else []) if not c["passed"]
        ],
        "candidate_error": after["error"] if after else None,
    }


def _latencies(run: dict) -> list[int]:
    return [r["latency_ms"] for r in run["results"] if r["latency_ms"] is not None]


def _tokens(run: dict) -> int:
    return sum((r["tokens_in"] or 0) + (r["tokens_out"] or 0) for r in run["results"])


def _avg(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def p95(values: list[int]) -> int | None:
    """95th percentile, nearest-rank method: the smallest value with >= 95% of values at or below it."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def _delta(base, candidate) -> dict:
    change = None if base is None or candidate is None else round(candidate - base, 4)
    return {"base": base, "candidate": candidate, "change": change}
