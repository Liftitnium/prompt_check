from dataclasses import replace

from fastapi.testclient import TestClient

from promptcheck.main import create_app
from promptcheck.prompts import service
from promptcheck.prompts.seed import load_seed

COUNT_QUERIES = {
    "prompts": "SELECT count(*) FROM prompts",
    "prompt_versions": "SELECT count(*) FROM prompt_versions",
    "test_cases": "SELECT count(*) FROM test_cases",
}


def _counts(conn):
    return {table: conn.execute(sql).fetchone()[0] for table, sql in COUNT_QUERIES.items()}


def test_seed_fills_an_empty_database(conn):
    assert load_seed(conn) is True
    assert _counts(conn) == {"prompts": 1, "prompt_versions": 2, "test_cases": 3}
    assert service.list_prompts(conn)[0]["name"] == "refund-reply"


def test_seed_is_idempotent(conn):
    load_seed(conn)
    before = _counts(conn)
    assert load_seed(conn) is False
    assert _counts(conn) == before


def test_seed_leaves_existing_user_data_alone(conn):
    service.create_prompt(conn, "my-prompt")
    assert load_seed(conn) is False
    assert [p["name"] for p in service.list_prompts(conn)] == ["my-prompt"]


def test_app_seeds_on_first_boot_only(settings):
    seeded = replace(settings, seed_demo=True)
    for _ in range(2):  # two boots on the same data directory
        with TestClient(create_app(seeded)) as c:
            names = [p["name"] for p in c.get("/prompts").json()]
    assert names == ["refund-reply"]


def test_seed_disabled_by_default_in_tests(client):
    assert client.get("/prompts").json() == []
