from contextlib import asynccontextmanager, closing

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from promptcheck.config import Settings, load_settings
from promptcheck.db import get_connection, init_db
from promptcheck.errors import DomainError
from promptcheck.prompts import repository as prompts_repo
from promptcheck.prompts.router import router as prompts_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings.db_path, schemas=[prompts_repo.SCHEMA])
        yield

    app = FastAPI(title="PromptCheck", lifespan=lifespan)
    app.state.settings = settings

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
    return app
