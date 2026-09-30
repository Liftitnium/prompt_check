"""HTTP layer for the prompts domain: parse the request, call the service, return JSON."""
import sqlite3

from fastapi import APIRouter, Depends, status

from promptcheck.db import get_db
from promptcheck.prompts import service
from promptcheck.prompts.check_specs import CHECK_SPECS
from promptcheck.prompts.schemas import (
    DiffOut, PromptCreate, PromptOut, TestCaseCreate, TestCaseOut, VersionCreate, VersionOut,
)

router = APIRouter(tags=["prompts"])


@router.post("/prompts", response_model=PromptOut, status_code=status.HTTP_201_CREATED)
def create_prompt(body: PromptCreate, conn: sqlite3.Connection = Depends(get_db)):
    return service.create_prompt(conn, body.name, body.description)


@router.get("/prompts", response_model=list[PromptOut])
def list_prompts(conn: sqlite3.Connection = Depends(get_db)):
    return service.list_prompts(conn)


@router.get("/prompts/{prompt_id}", response_model=PromptOut)
def get_prompt(prompt_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.get_prompt(conn, prompt_id)


@router.post(
    "/prompts/{prompt_id}/versions",
    response_model=VersionOut, status_code=status.HTTP_201_CREATED,
)
def publish_version(
    prompt_id: int, body: VersionCreate, conn: sqlite3.Connection = Depends(get_db)
):
    return service.publish_version(conn, prompt_id, body.template, body.model, body.notes)


@router.get("/prompts/{prompt_id}/versions", response_model=list[VersionOut])
def list_versions(prompt_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.list_versions(conn, prompt_id)


@router.get("/prompts/{prompt_id}/versions/{version}", response_model=VersionOut)
def get_version(prompt_id: int, version: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.get_version(conn, prompt_id, version)


@router.get("/prompts/{prompt_id}/versions/{a}/diff/{b}", response_model=DiffOut)
def diff_versions(prompt_id: int, a: int, b: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.diff_versions(conn, prompt_id, a, b)


@router.post(
    "/prompts/{prompt_id}/test-cases",
    response_model=TestCaseOut, status_code=status.HTTP_201_CREATED,
)
def add_test_case(
    prompt_id: int, body: TestCaseCreate, conn: sqlite3.Connection = Depends(get_db)
):
    checks = [check.model_dump(exclude_none=True) for check in body.checks]
    return service.add_test_case(conn, prompt_id, body.name, body.inputs, checks)


@router.get("/prompts/{prompt_id}/test-cases", response_model=list[TestCaseOut])
def list_test_cases(prompt_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return service.list_test_cases(conn, prompt_id)


@router.delete("/test-cases/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_test_case(test_case_id: int, conn: sqlite3.Connection = Depends(get_db)):
    service.archive_test_case(conn, test_case_id)


@router.get("/checks")
def list_check_types():
    """The check types a test case may use, and the arg type each expects."""
    return {name: (t.__name__ if t else None) for name, t in CHECK_SPECS.items()}
