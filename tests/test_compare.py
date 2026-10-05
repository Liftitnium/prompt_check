import pytest

from promptcheck.errors import InvalidInputError
from promptcheck.evals.compare import compare_runs, p95


def result(case_id, status, latency=100, tokens=(10, 5), failed=()):
    return {
        "test_case_id": case_id, "test_case_name": f"case {case_id}", "status": status,
        "latency_ms": latency, "tokens_in": tokens[0], "tokens_out": tokens[1],
        "error": "LLM call failed: boom" if status == "error" else None,
        "check_details": [{"type": "contains", "passed": False, "detail": d} for d in failed],
    }


def run(run_id, version, results, prompt_id=1, status="completed"):
    passed = sum(r["status"] == "pass" for r in results)
    return {"id": run_id, "prompt_id": prompt_id, "version": version, "status": status,
            "pass_rate": passed / len(results), "results": results}


def test_every_category_is_detected():
    base = run(1, 1, [result(1, "pass"), result(2, "fail"), result(3, "pass"),
                      result(4, "fail"), result(5, "pass")])
    cand = run(2, 2, [result(1, "fail", failed=["missing 'reembolso'"]), result(2, "pass"),
                      result(3, "pass"), result(4, "error"), result(6, "pass")])
    report = compare_runs(base, cand)

    assert report["summary"] == {"regressed": 1, "fixed": 1, "still_passing": 1,
                                 "still_failing": 1, "new": 1, "removed": 1}
    [regressed] = report["cases"]["regressed"]
    assert regressed["test_case_id"] == 1
    assert regressed["candidate_failed_checks"] == ["missing 'reembolso'"]
    assert report["cases"]["still_failing"][0]["candidate_error"] == "LLM call failed: boom"
    assert report["cases"]["removed"][0]["candidate_status"] is None
    assert report["cases"]["new"][0]["base_status"] is None


def test_any_regression_blocks_even_if_pass_rate_improves():
    base = run(1, 1, [result(1, "pass"), result(2, "fail"), result(3, "fail")])
    cand = run(2, 2, [result(1, "fail"), result(2, "pass"), result(3, "pass")])
    report = compare_runs(base, cand)
    assert report["metrics"]["pass_rate"]["change"] > 0
    assert report["verdict"] == "block"


def test_no_regressions_and_no_drop_ships():
    base = run(1, 1, [result(1, "pass"), result(2, "fail")])
    cand = run(2, 2, [result(1, "pass"), result(2, "pass")])
    report = compare_runs(base, cand)
    assert report["verdict"] == "ship"
    assert (report["base_version"], report["candidate_version"]) == (1, 2)


def test_lower_pass_rate_blocks_without_regressions():
    # a newly added failing case lowers the pass rate without any case regressing
    base = run(1, 1, [result(1, "pass")])
    cand = run(2, 2, [result(1, "pass"), result(2, "fail")])
    assert compare_runs(base, cand)["verdict"] == "block"


def test_latency_and_token_metrics():
    base = run(1, 1, [result(1, "pass", latency=100), result(2, "pass", latency=300)])
    cand = run(2, 2, [result(1, "pass", latency=50, tokens=(4, 1)),
                      result(2, "error", latency=None, tokens=(0, 0))])
    metrics = compare_runs(base, cand)["metrics"]
    assert metrics["avg_latency_ms"] == {"base": 200.0, "candidate": 50.0, "change": -150.0}
    assert metrics["p95_latency_ms"] == {"base": 300, "candidate": 50, "change": -250}
    assert metrics["total_tokens"] == {"base": 30, "candidate": 5, "change": -25}


def test_metrics_are_none_when_no_latency_recorded():
    base = run(1, 1, [result(1, "error", latency=None)])
    cand = run(2, 2, [result(1, "pass")])
    assert compare_runs(base, cand)["metrics"]["avg_latency_ms"]["change"] is None


def test_p95_nearest_rank():
    assert p95([]) is None
    assert p95([7]) == 7
    assert p95(list(range(1, 21))) == 19   # ceil(0.95 * 20) = 19th value
    assert p95([5, 1, 3]) == 5              # unsorted input is fine


def test_runs_of_different_prompts_cannot_be_compared():
    with pytest.raises(InvalidInputError, match="same prompt"):
        compare_runs(run(1, 1, [result(1, "pass")]), run(2, 1, [result(1, "pass")], prompt_id=2))


def test_unfinished_runs_cannot_be_compared():
    with pytest.raises(InvalidInputError, match="run 2 is running"):
        compare_runs(run(1, 1, [result(1, "pass")]),
                     run(2, 2, [result(1, "pass")], status="running"))
