"""Health, CORS, config and migrations: the parts every service must get right."""
from dataclasses import replace

import pymssql
import pytest
from fastapi.testclient import TestClient

from app import config
from app.db import _batches, _connect_args, connect, migrate
from app.main import MIGRATIONS_DIR, create_app

UNREACHABLE = "mssql://nobody:nothing@127.0.0.1:1/nowhere"


def test_health_ok_reports_db_and_version(settings, gateway):
    with TestClient(create_app(replace(settings, version="abc123"), gateway=gateway)) as c:
        response = c.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "version": "abc123"}


def test_health_503_when_database_unreachable():
    # no `with`: startup (which would need the database) is not run
    c = TestClient(create_app(config.Settings(database_url=UNREACHABLE)))
    response = c.get("/health")
    assert response.status_code == 503
    assert response.json()["db"] == "unreachable"
    assert set(response.json()) == {"status", "db", "version"}


def test_cors_allows_only_the_ui_origin():
    c = TestClient(create_app(config.Settings(database_url=UNREACHABLE,
                                              allowed_origins=("http://localhost:8080",))))
    preflight = {"Access-Control-Request-Method": "GET"}
    ok = c.options("/runs", headers={"Origin": "http://localhost:8080", **preflight})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:8080"
    bad = c.options("/runs", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in bad.headers


def test_migrations_are_recorded_and_not_rerun(settings):
    conn = connect(settings.database_url)
    assert migrate(conn, MIGRATIONS_DIR) == ["001_init.sql"]
    assert migrate(conn, MIGRATIONS_DIR) == []
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    assert [r["version"] for r in rows] == ["001_init.sql"]
    conn.close()


def test_failed_migration_leaves_nothing_behind(settings, tmp_path):
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE ok_table (id INT)")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE half (id INT)\nGO\nSELECT * FROM missing_table")
    conn = connect(settings.database_url)
    with pytest.raises(pymssql.Error):
        migrate(conn, tmp_path)
    applied = [r["version"] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()]
    assert applied == ["001_ok.sql"]
    assert conn.execute("SELECT OBJECT_ID('half') AS id").fetchone()["id"] is None
    conn.close()


def test_batches_split_on_go_lines():
    assert _batches("A\nGO\n\nB\ngo\n") == ["A", "\nB"]


def test_database_url_parsing():
    args = _connect_args("mssql://prompts_app:p%40ss@db.example:14330/prompts")
    assert (args["server"], args["port"], args["user"], args["password"], args["database"]) == (
        "db.example", "14330", "prompts_app", "p@ss", "prompts")
    with pytest.raises(ValueError):
        _connect_args("postgres://u:p@h/db")


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE)
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://a.example/, http://b.example")
    monkeypatch.setenv("GIT_SHA", "deadbeef")
    monkeypatch.setenv("PROMPTS_URL", "http://prompts.internal:9000")
    monkeypatch.setenv("PROMPTS_TIMEOUT_S", "0.5")
    monkeypatch.setenv("LLM_API_KEY", "")
    s = config.load_settings()
    assert s.allowed_origins == ("http://a.example", "http://b.example")
    assert (s.version, s.port, s.llm_provider, s.llm_api_key) == ("deadbeef", 8000, "fake", None)
    assert (s.prompts_url, s.prompts_timeout_s) == ("http://prompts.internal:9000", 0.5)


def test_load_settings_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        config.load_settings()


def test_startup_fails_interrupted_runs(settings, gateway, conn):
    from app import repository as repo
    run_id = repo.insert_run(conn, 1, 1, 1, "Hi", "m", "fake", total=0)
    conn.commit()
    with TestClient(create_app(settings, gateway=gateway)) as c:
        assert c.get(f"/runs/{run_id}").json()["status"] == "failed"
