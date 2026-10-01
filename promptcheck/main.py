from contextlib import asynccontextmanager, closing

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from promptcheck.config import Settings, load_settings
from promptcheck.db import get_connection, init_db
from promptcheck.errors import DomainError
from promptcheck.evals import repository as evals_repo
from promptcheck.evals import runner
from promptcheck.evals.llm_client import build_llm_client
from promptcheck.evals.router import router as evals_router
from promptcheck.prompts import repository as prompts_repo
from promptcheck.prompts.router import router as prompts_router

SCHEMAS = [prompts_repo.SCHEMA, evals_repo.SCHEMA]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings.db_path, SCHEMAS)
        with closing(get_connection(settings.db_path)) as conn:
            runner.recover_interrupted_runs(conn)
        yield

    app = FastAPI(title="PromptCheck", lifespan=lifespan)
    app.state.settings = settings
    app.state.llm = build_llm_client(settings)

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        # one place that turns service errors into HTTP responses
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        with closing(get_connection(settings.db_path)) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}

    app.include_router(prompts_router)
    app.include_router(evals_router)
    return app
