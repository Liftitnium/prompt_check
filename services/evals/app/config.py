"""All configuration comes from environment variables; nothing is hardcoded per environment."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    host: str = "0.0.0.0"
    port: int = 8000
    # the browser origins allowed to call this API (the UI), comma-separated in env
    allowed_origins: tuple[str, ...] = ("http://localhost:8080",)
    version: str = "dev"
    # where the prompts service lives, and how long to wait for it before giving up
    prompts_url: str = "http://prompts:8000"
    prompts_timeout_s: float = 2.0
    llm_provider: str = "fake"
    llm_api_key: str | None = None
    llm_model: str = "claude-opus-5"
    llm_concurrency: int = 4
    # startup waits for the database: SQL Server boot or Azure serverless resume
    db_connect_attempts: int = 10


def _origins(raw: str) -> tuple[str, ...]:
    return tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        # fail at boot, not on the first request
        raise RuntimeError("DATABASE_URL is not set")
    return Settings(
        database_url=database_url,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        allowed_origins=_origins(os.environ.get("ALLOWED_ORIGINS", "http://localhost:8080")),
        version=os.environ.get("GIT_SHA", "dev"),
        prompts_url=os.environ.get("PROMPTS_URL", "http://prompts:8000"),
        prompts_timeout_s=float(os.environ.get("PROMPTS_TIMEOUT_S", "2")),
        llm_provider=os.environ.get("LLM_PROVIDER", "fake"),
        llm_api_key=os.environ.get("LLM_API_KEY") or None,
        llm_model=os.environ.get("LLM_MODEL", "claude-opus-5"),
        llm_concurrency=int(os.environ.get("LLM_CONCURRENCY", "4")),
        db_connect_attempts=int(os.environ.get("DB_CONNECT_ATTEMPTS", "10")),
    )
