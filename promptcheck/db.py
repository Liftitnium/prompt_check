"""SQLite connection helpers. Each domain passes in its own schema SQL."""
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

from fastapi import Request


def get_connection(db_path: Path) -> sqlite3.Connection:
    # check_same_thread=False: FastAPI may open the connection in one worker
    # thread and run the endpoint in another. Each request still gets its own.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path, schemas: list[str]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(get_connection(db_path)) as conn, conn:
        # WAL lets readers (the dashboard) read while a run is writing results.
        conn.execute("PRAGMA journal_mode = WAL")
        for schema in schemas:
            conn.executescript(schema)


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI dependency: one connection per request, committed on success."""
    conn = get_connection(request.app.state.settings.db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
