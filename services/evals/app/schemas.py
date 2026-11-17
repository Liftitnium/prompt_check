"""Request/response shapes for the evals API."""
from typing import Literal

from pydantic import BaseModel


class RunCreate(BaseModel):
    prompt_version_id: int


class CheckDetail(BaseModel):
    type: str
    passed: bool
    detail: str


class ResultOut(BaseModel):
    id: int
    test_case_id: int
    test_case_name: str
    inputs: dict[str, str]
    checks: list[dict]
    status: str
    rendered_prompt: str | None
    output: str | None
    check_details: list[CheckDetail]
    error: str | None
    latency_ms: int | None
    tokens_in: int | None
    tokens_out: int | None


class RunOut(BaseModel):
    id: int
    prompt_id: int
    prompt_version_id: int
    version: int
    model: str
    provider: str
    status: str
    total: int
    passed: int
    failed: int
    errored: int
    pass_rate: float | None
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class RunDetailOut(RunOut):
    template_snapshot: str
    results: list[ResultOut]


# ---- shared by every route, so the OpenAPI document lists the errors the API really returns

class ErrorOut(BaseModel):
    """Body of every error. detail is a message, or FastAPI's list of field errors on a 422."""
    detail: str | list[dict]


class HealthOut(BaseModel):
    status: str
    db: str
    version: str


_ERROR_DESCRIPTIONS = {
    404: "Not found",
    422: "Invalid input",
    502: "The prompts service answered with an unexpected error",
    503: "The prompts service is unavailable or timed out",
}


def errors(*codes: int) -> dict:
    """The `responses=` argument for a route that can fail with these status codes."""
    return {code: {"model": ErrorOut, "description": _ERROR_DESCRIPTIONS[code]} for code in codes}


# ---- GET /runs/compare

class MetricDelta(BaseModel):
    base: int | float | None
    candidate: int | float | None
    change: int | float | None


class CaseSummary(BaseModel):
    test_case_id: int
    test_case_name: str
    base_status: str | None
    candidate_status: str | None
    candidate_failed_checks: list[str]
    candidate_error: str | None


class CompareSummary(BaseModel):
    regressed: int
    fixed: int
    still_passing: int
    still_failing: int
    new: int
    removed: int


class CompareMetrics(BaseModel):
    pass_rate: MetricDelta
    avg_latency_ms: MetricDelta
    p95_latency_ms: MetricDelta
    total_tokens: MetricDelta


class CompareCases(BaseModel):
    regressed: list[CaseSummary]
    fixed: list[CaseSummary]
    still_passing: list[CaseSummary]
    still_failing: list[CaseSummary]
    new: list[CaseSummary]
    removed: list[CaseSummary]


class CompareOut(BaseModel):
    base_run_id: int
    candidate_run_id: int
    base_version: int
    candidate_version: int
    verdict: Literal["ship", "block"]
    summary: CompareSummary
    metrics: CompareMetrics
    cases: CompareCases
