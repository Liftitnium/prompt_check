"""Request/response shapes for the evals API."""
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
