"""SQL for the prompts domain. No business rules here, only reads and writes."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS prompts (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id         INTEGER PRIMARY KEY,
    prompt_id  INTEGER NOT NULL REFERENCES prompts(id),
    version    INTEGER NOT NULL,
    template   TEXT NOT NULL,
    model      TEXT,
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (prompt_id, version)
);

CREATE TABLE IF NOT EXISTS test_cases (
    id         INTEGER PRIMARY KEY,
    prompt_id  INTEGER NOT NULL REFERENCES prompts(id),
    name       TEXT NOT NULL,
    inputs     TEXT NOT NULL,
    checks     TEXT NOT NULL,
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


def insert_prompt(conn: sqlite3.Connection, name: str, description: str) -> int:
    cur = conn.execute(
        "INSERT INTO prompts (name, description) VALUES (?, ?)", (name, description)
    )
    return cur.lastrowid


def get_prompt(conn: sqlite3.Connection, prompt_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM prompts WHERE id = ?", (prompt_id,)).fetchone()


def get_prompt_by_name(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM prompts WHERE name = ?", (name,)).fetchone()


def list_prompts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT p.*,
               (SELECT MAX(version) FROM prompt_versions v WHERE v.prompt_id = p.id)
                   AS latest_version,
               (SELECT COUNT(*) FROM test_cases t WHERE t.prompt_id = p.id AND t.archived = 0)
                   AS test_case_count
        FROM prompts p
        ORDER BY p.name
        """
    ).fetchall()


def get_latest_version(conn: sqlite3.Connection, prompt_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM prompt_versions WHERE prompt_id = ? ORDER BY version DESC LIMIT 1",
        (prompt_id,),
    ).fetchone()


def insert_version(
    conn: sqlite3.Connection, prompt_id: int, version: int, template: str,
    model: str | None, notes: str,
) -> int:
    cur = conn.execute(
        """INSERT INTO prompt_versions (prompt_id, version, template, model, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (prompt_id, version, template, model, notes),
    )
    return cur.lastrowid


def get_version(conn: sqlite3.Connection, prompt_id: int, version: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM prompt_versions WHERE prompt_id = ? AND version = ?",
        (prompt_id, version),
    ).fetchone()


def get_version_by_id(conn: sqlite3.Connection, version_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM prompt_versions WHERE id = ?", (version_id,)
    ).fetchone()


def list_versions(conn: sqlite3.Connection, prompt_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM prompt_versions WHERE prompt_id = ? ORDER BY version",
        (prompt_id,),
    ).fetchall()


def insert_test_case(
    conn: sqlite3.Connection, prompt_id: int, name: str, inputs_json: str, checks_json: str
) -> int:
    cur = conn.execute(
        "INSERT INTO test_cases (prompt_id, name, inputs, checks) VALUES (?, ?, ?, ?)",
        (prompt_id, name, inputs_json, checks_json),
    )
    return cur.lastrowid


def get_test_case(conn: sqlite3.Connection, test_case_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM test_cases WHERE id = ?", (test_case_id,)
    ).fetchone()


def list_active_test_cases(conn: sqlite3.Connection, prompt_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM test_cases WHERE prompt_id = ? AND archived = 0 ORDER BY id",
        (prompt_id,),
    ).fetchall()


def archive_test_case(conn: sqlite3.Connection, test_case_id: int) -> None:
    conn.execute("UPDATE test_cases SET archived = 1 WHERE id = ?", (test_case_id,))
