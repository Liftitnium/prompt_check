import pytest
from fastapi.testclient import TestClient

from promptcheck.config import Settings
from promptcheck.db import get_connection, init_db
from promptcheck.main import create_app
from promptcheck.main import SCHEMAS


@pytest.fixture
def settings(tmp_path):
    return Settings("0.0.0.0", 8000, tmp_path / "data", "fake", None)


@pytest.fixture
def conn(settings):
    """A fresh SQLite database with all schemas, for service-level tests."""
    init_db(settings.db_path, schemas=SCHEMAS)
    connection = get_connection(settings.db_path)
    yield connection
    connection.close()


@pytest.fixture
def client(settings):
    """A test HTTP client against an app using a temporary database."""
    with TestClient(create_app(settings)) as c:
        yield c
