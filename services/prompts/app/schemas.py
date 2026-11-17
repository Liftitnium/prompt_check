"""Request/response shapes for the prompts API (validated by Pydantic)."""
from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class PromptOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: str
    latest_version: int | None = None
    test_case_count: int | None = None


class VersionCreate(BaseModel):
    template: str = Field(min_length=1)
    model: str | None = None
    notes: str = ""


class VersionOut(BaseModel):
    id: int
    prompt_id: int
    version: int
    template: str
    model: str | None
    notes: str
    variables: list[str]
    created_at: str


class DiffOut(BaseModel):
    from_version: int
    to_version: int
    added: int
    removed: int
    model_changed: bool
    diff: list[str]


class Check(BaseModel):
    type: str
    arg: str | int | list[str] | None = None


class TestCaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    inputs: dict[str, str] = {}
    checks: list[Check] = Field(min_length=1)


class TestCaseOut(BaseModel):
    id: int
    prompt_id: int
    name: str
    inputs: dict[str, str]
    checks: list[Check]
    archived: bool
    created_at: str


class VersionForRunOut(VersionOut):
    """Contract with the evals service (GET /versions/{id}/for-run)."""
    test_cases: list[TestCaseOut]


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
    409: "Conflicts with existing data",
    422: "Invalid input",
}


def errors(*codes: int) -> dict:
    """The `responses=` argument for a route that can fail with these status codes."""
    return {code: {"model": ErrorOut, "description": _ERROR_DESCRIPTIONS[code]} for code in codes}
