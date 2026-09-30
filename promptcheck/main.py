from contextlib import asynccontextmanager

from fastapi import FastAPI

from promptcheck.config import Settings, load_settings
from promptcheck.db import get_connection, init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings.db_path, schemas=[])
        yield

    app = FastAPI(title="PromptCheck", lifespan=lifespan)
    app.state.settings = settings

    @app.get("/health")
    def health():
        with get_connection(settings.db_path) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}

    return app
