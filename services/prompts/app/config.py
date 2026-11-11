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
    # off unless set, so tests start from an empty database; load_settings turns it on
    seed_demo: bool = False
    # startup waits for the database: SQL Server boot or Azure serverless resume
    db_connect_attempts: int = 10


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).lower() not in ("0", "false", "no")


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
        seed_demo=_flag("SEED_DEMO", "true"),
        db_connect_attempts=int(os.environ.get("DB_CONNECT_ATTEMPTS", "10")),
    )
