"""All configuration comes from environment variables (container contract §7.9)."""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    data_dir: Path
    llm_provider: str
    llm_api_key: str | None
    llm_model: str = "claude-opus-5"
    llm_concurrency: int = 4
    # off unless set, so tests start from an empty database; load_settings turns it on
    seed_demo: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "promptcheck.db"


def load_settings() -> Settings:
    return Settings(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        data_dir=Path(os.environ.get("DATA_DIR", "./data")),
        llm_provider=os.environ.get("LLM_PROVIDER", "fake"),
        llm_api_key=os.environ.get("LLM_API_KEY"),
        llm_model=os.environ.get("LLM_MODEL", "claude-opus-5"),
        llm_concurrency=int(os.environ.get("LLM_CONCURRENCY", "4")),
        seed_demo=os.environ.get("SEED_DEMO", "true").lower() not in ("0", "false", "no"),
    )
