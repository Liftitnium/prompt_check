"""SQL Server connections and versioned migrations.

DATABASE_URL looks like mssql://user:password@host:1433/database. Rows come back as
dicts and datetimes as ISO strings, so the rest of the code never sees a driver type.
"""
import logging
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymssql
from fastapi import Request

log = logging.getLogger(__name__)


class Result:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> dict | None:
        row = self._cursor.fetchone()
        return _clean(row) if row else None

    def fetchall(self) -> list[dict]:
        return [_clean(row) for row in self._cursor.fetchall()]


class Connection:
    """A pymssql connection with the small execute() API the repositories use."""

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params: tuple = ()) -> Result:
        cursor = self.raw.cursor(as_dict=True)
        # pymssql only treats % as a placeholder when params are given
        cursor.execute(sql, params or None)
        return Result(cursor)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()


def _clean(row: dict) -> dict:
    # every timestamp is stored in UTC, so it is safe to label it with Z
    return {
        key: value.strftime("%Y-%m-%dT%H:%M:%SZ") if isinstance(value, datetime) else value
        for key, value in row.items()
    }


def _connect_args(url: str, login_timeout: int = 15) -> dict:
    parts = urlparse(url)
    if not parts.scheme.startswith("mssql") or not parts.hostname or not parts.path.strip("/"):
        raise ValueError("DATABASE_URL must look like mssql://user:password@host:1433/database")
    return {
        "server": parts.hostname,
        "port": str(parts.port or 1433),
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.strip("/"),
        "login_timeout": login_timeout,
    }


def connect(url: str, attempts: int = 1, login_timeout: int = 15) -> Connection:
    """Open a connection, retrying with backoff.

    SQL Server takes ~20 s to start in compose, and Azure SQL serverless takes up to
    a minute to resume after auto-pause (error 40613), so callers that run at startup
    ask for several attempts.
    """
    args = _connect_args(url, login_timeout)
    for attempt in range(1, attempts + 1):
        try:
            return Connection(pymssql.connect(**args))
        except pymssql.OperationalError as e:
            if attempt == attempts:
                raise
            delay = min(2 ** attempt, 15)
            log.warning("database not reachable (attempt %d/%d), retrying in %ds: %s",
                        attempt, attempts, delay, e)
            time.sleep(delay)
    raise AssertionError("unreachable")


def get_db(request: Request) -> Iterator[Connection]:
    """FastAPI dependency: one connection per request, committed on success."""
    conn = connect(request.app.state.settings.database_url, attempts=3)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- migrations ----------

MIGRATIONS_TABLE = """
IF OBJECT_ID('schema_migrations') IS NULL
    CREATE TABLE schema_migrations (
        version    NVARCHAR(255) NOT NULL PRIMARY KEY,
        applied_at DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    )
"""


def _batches(script: str) -> list[str]:
    """Split a migration on lines that say GO, like sqlcmd does."""
    batches, current = [], []
    for line in script.splitlines():
        if line.strip().upper() == "GO":
            batches.append("\n".join(current))
            current = []
        else:
            current.append(line)
    batches.append("\n".join(current))
    return [b for b in batches if b.strip()]


def migrate(conn: Connection, folder: Path) -> list[str]:
    """Apply every migrations/*.sql file not yet recorded in schema_migrations, in name order.

    Each file runs in one transaction together with its schema_migrations row, so a
    failed migration leaves nothing half-applied and is retried on the next boot.
    Applied files are never edited; a fix is a new file.
    """
    conn.execute(MIGRATIONS_TABLE)
    conn.commit()
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations").fetchall()}
    newly_applied = []
    for path in sorted(folder.glob("*.sql")):
        if path.name in applied:
            continue
        try:
            for batch in _batches(path.read_text(encoding="utf-8")):
                conn.execute(batch)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (path.name,))
            conn.commit()
        except Exception:
            conn.rollback()
            log.exception("migration %s failed; nothing from it was kept", path.name)
            raise
        log.info("applied migration %s", path.name)
        newly_applied.append(path.name)
    if not newly_applied:
        log.info("database schema up to date (%d migrations applied)", len(applied))
    return newly_applied


def check_health(conn: Connection) -> None:
    """Raise unless this login can read and write its own database.

    The UPDATE matches no rows, so it changes nothing, but it still needs write
    permission on the table.
    """
    conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()
    conn.execute("UPDATE schema_migrations SET applied_at = applied_at WHERE 1 = 0")
    conn.rollback()
