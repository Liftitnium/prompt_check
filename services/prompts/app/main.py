"""The prompts service: prompts, immutable versions and test cases, in its own database."""
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, load_settings
from app.db import check_health, connect, migrate
from app.errors import DomainError
from app.router import router
from app.seed import load_seed

log = logging.getLogger("prompts")
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = connect(settings.database_url, attempts=settings.db_connect_attempts)
        try:
            migrate(conn, MIGRATIONS_DIR)
            if settings.seed_demo and load_seed(conn):
                conn.commit()
                log.info("loaded demo data into an empty database")
        finally:
            conn.close()
        yield

    app = FastAPI(title="PromptCheck prompts service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings

    # only the UI's origin may call this API from a browser
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST", "DELETE"],
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
