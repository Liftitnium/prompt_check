from pathlib import Path

from promptcheck.config import load_settings


def test_defaults(monkeypatch):
    for var in ["HOST", "PORT", "DATA_DIR", "LLM_PROVIDER", "LLM_API_KEY"]:
        monkeypatch.delenv(var, raising=False)
    s = load_settings()
    assert s.host == "0.0.0.0"
    assert s.port == 8000
    assert s.llm_provider == "fake"
    assert s.db_path == Path("./data/promptcheck.db")


def test_reads_env(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    s = load_settings()
    assert s.port == 9000
    assert s.db_path == tmp_path / "promptcheck.db"
