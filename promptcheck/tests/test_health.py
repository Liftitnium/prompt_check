from fastapi.testclient import TestClient

from promptcheck.config import Settings
from promptcheck.main import create_app


def test_health_creates_db(tmp_path):
    settings = Settings("0.0.0.0", 8000, tmp_path / "data", "fake", None)
    with TestClient(create_app(settings)) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert settings.db_path.exists()
