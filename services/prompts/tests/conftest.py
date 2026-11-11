"""Tests run against a real SQL Server database named by TEST_DATABASE_URL.

Locally: docker compose up -d sqlserver, then e.g.
TEST_DATABASE_URL=mssql://sa:<SA_PASSWORD>@localhost:1433/promptcheck_test_prompts
CI starts its own SQL Server container. The database is created if missing, and every
test starts from an empty schema built by the real migrations.
"""
import os
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connect, migrate
from app.main import MIGRATIONS_DIR, create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

CREATE_DATABASE = """
DECLARE @name SYSNAME = %s;
DECLARE @sql NVARCHAR(MAX);
IF DB_ID(@name) IS NULL
BEGIN
    SET @sql = N'CREATE DATABASE ' + QUOTENAME(@name);
    EXEC (@sql);
    SET @sql = N'ALTER DATABASE ' + QUOTENAME(@name) + N' SET READ_COMMITTED_SNAPSHOT ON';
    EXEC (@sql);
END
"""

# drop foreign keys first, then every table, so migrations rebuild from nothing
DROP_EVERYTHING = """
DECLARE @sql NVARCHAR(MAX) = N'';
SELECT @sql += N'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id)) + N'.'
             + QUOTENAME(OBJECT_NAME(parent_object_id)) + N' DROP CONSTRAINT ' + QUOTENAME(name) + N';'
FROM sys.foreign_keys;
EXEC sp_executesql @sql;
SET @sql = N'';
SELECT @sql += N'DROP TABLE ' + QUOTENAME(SCHEMA_NAME(schema_id)) + N'.' + QUOTENAME(name) + N';'
FROM sys.tables;
EXEC sp_executesql @sql;
"""


@pytest.fixture(scope="session")
def database_url():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is not set; database tests need SQL Server")
    parts = urlparse(TEST_DATABASE_URL)
    master = connect(parts._replace(path="/master").geturl(), attempts=10)
    master.raw.autocommit(True)  # CREATE DATABASE cannot run inside a transaction
    master.execute(CREATE_DATABASE, (parts.path.strip("/"),))
    master.close()
    return TEST_DATABASE_URL


@pytest.fixture
def settings(database_url):
    conn = connect(database_url)
    conn.execute(DROP_EVERYTHING)
    conn.commit()
    conn.close()
    return Settings(database_url=database_url, db_connect_attempts=1)


@pytest.fixture
def conn(settings):
    """A migrated, empty database, for service-level tests."""
    connection = connect(settings.database_url)
    migrate(connection, MIGRATIONS_DIR)
    yield connection
    connection.rollback()
    connection.close()


@pytest.fixture
def client(settings):
    """A test HTTP client; entering it runs startup, which applies the migrations."""
    with TestClient(create_app(settings)) as c:
        yield c
