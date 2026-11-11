"""The evals service: runs a prompt version's test cases against an LLM and scores them.

It owns its own database and gets prompt data only from the prompts service, over
HTTP (gateway.py). If the prompts service is down, starting or re-scoring a run
answers 503, but every stored run can still be listed, opened and compared.
"""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import runner
from app.config import Settings, load_settings
from app.db import check_health, connect, migrate
from app.errors import DomainError
from app.gateway import HttpPromptsGateway, PromptsGateway
from app.judge import build_judge
from app.llm_client import build_llm_client
from app.router import router

log = logging.getLogger("evals")
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def create_app(settings: Settings | None = None, gateway: PromptsGateway | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = connect(settings.database_url, attempts=settings.db_connect_attempts)
        try:
            migrate(conn, MIGRATIONS_DIR)
            # background runs die with the process, so any left running can never finish
            if count := runner.recover_interrupted_runs(conn):
                log.warning("marked %d interrupted run(s) as failed", count)
        finally:
            conn.close()
        yield

    app = FastAPI(title="PromptCheck evals service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    app.state.gateway = gateway or HttpPromptsGateway(settings.prompts_url, settings.prompts_timeout_s)
    app.state.llm = build_llm_client(settings)
    app.state.judge = build_judge(settings, app.state.llm)

    # only the UI's origin may call this API from a browser
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("%s %s failed", request.method, request.url.path)
            raise
        ms = (time.perf_counter() - start) * 1000
        log.info("%s %s %d %.0fms", request.method, request.url.path, response.status_code, ms)
        return response

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        # one place that turns service errors into HTTP responses
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        # only this service's own database: a prompts outage must not make evals look dead
        try:
            conn = connect(settings.database_url, login_timeout=3)
            try:
                check_health(conn)
            finally:
                conn.close()
        except Exception as e:
            log.warning("health check: database unavailable: %s", e)
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "db": "unreachable", "version": settings.version},
            )
        return {"status": "ok", "db": "ok", "version": settings.version}

    app.include_router(router)
    return app
