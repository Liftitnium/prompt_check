"""HTTP layer for the evals domain."""
import sqlite3

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from promptcheck.db import get_db
from promptcheck.evals import runner
from promptcheck.evals.compare import compare_runs
from promptcheck.evals.gateway import InProcessPromptsGateway
from promptcheck.evals.schemas import RunCreate, RunDetailOut, RunOut

router = APIRouter(tags=["evals"])


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
def start_run(
    body: RunCreate, request: Request, background: BackgroundTasks,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Create a run and return immediately (202). The LLM calls happen in the background;
    poll GET /runs/{id} until status is 'completed' or 'failed'."""
    settings = request.app.state.settings
    llm = request.app.state.llm
    run = runner.create_run(
        conn, InProcessPromptsGateway(settings.db_path), body.prompt_version_id,
        provider=llm.name, default_model=settings.llm_model,
    )
    conn.commit()  # the background task opens its own connection, so the run must be saved first
    background.add_task(
        runner.execute_run, settings.db_path, run["id"], llm, settings.llm_concurrency,
        request.app.state.judge,
    )
    return run


@router.get("/runs", response_model=list[RunOut])
def list_runs(prompt_id: int | None = None, conn: sqlite3.Connection = Depends(get_db)):
    return runner.list_runs(conn, prompt_id)


# declared before /runs/{run_id}, otherwise "compare" would be parsed as a run id
@router.get("/runs/compare")
def compare(base: int, candidate: int, conn: sqlite3.Connection = Depends(get_db)):
    """Compare a candidate run against a base run of the same prompt: regressions,
    fixes, pass-rate/latency/token deltas and a ship/block verdict."""
    return compare_runs(
        runner.get_run(conn, base, with_results=True),
        runner.get_run(conn, candidate, with_results=True),
    )


@router.post("/runs/{run_id}/rescore", response_model=RunDetailOut,
             status_code=status.HTTP_201_CREATED)
async def rescore(run_id: int, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    """Re-score a completed run's stored outputs against the current checks, as a new run.
    No new outputs are generated (only llm_judge checks call the judge), so it answers in one request."""
    settings = request.app.state.settings
    return await runner.rescore_run(
        conn, InProcessPromptsGateway(settings.db_path), run_id, request.app.state.judge
    )


@router.get("/runs/{run_id}", response_model=RunDetailOut)
def get_run(run_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return runner.get_run(conn, run_id, with_results=True)
