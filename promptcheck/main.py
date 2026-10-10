from contextlib import asynccontextmanager, closing
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from promptcheck.config import Settings, load_settings
from promptcheck.db import get_connection, init_db
from promptcheck.errors import DomainError
from promptcheck.evals import repository as evals_repo
from promptcheck.evals import runner
from promptcheck.evals.judge import build_judge
from promptcheck.evals.llm_client import build_llm_client
from promptcheck.evals.router import router as evals_router
from promptcheck.prompts import repository as prompts_repo
from promptcheck.prompts.seed import load_seed
from promptcheck.prompts.router import router as prompts_router

SCHEMAS = [prompts_repo.SCHEMA, evals_repo.SCHEMA]
STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # create what is missing, never drop: existing data survives every restart
        init_db(settings.db_path, SCHEMAS)
        with closing(get_connection(settings.db_path)) as conn:
            runner.recover_interrupted_runs(conn)
        if settings.seed_demo:
            with closing(get_connection(settings.db_path)) as conn, conn:
                load_seed(conn)
        yield

    app = FastAPI(title="PromptCheck", lifespan=lifespan)
    app.state.settings = settings
    app.state.llm = build_llm_client(settings)
    app.state.judge = build_judge(settings, app.state.llm)

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        # one place that turns service errors into HTTP responses
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/", include_in_schema=False)
    def root():
        # the UI is static HTML/CSS/JS calling the JSON API: no build step, no extra dependency
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health():
        with closing(get_connection(settings.db_path)) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}

    app.include_router(prompts_router)
    app.include_router(evals_router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app
