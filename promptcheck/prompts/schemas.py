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
