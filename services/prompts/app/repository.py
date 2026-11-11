"""SQL for the prompts domain. No business rules here, only reads and writes.

The schema lives in migrations/*.sql, not here.
"""
from app.db import Connection


def insert_prompt(conn: Connection, name: str, description: str) -> int:
    return conn.execute(
        "INSERT INTO prompts (name, description) OUTPUT INSERTED.id VALUES (%s, %s)",
        (name, description),
    ).fetchone()["id"]


def get_prompt(conn: Connection, prompt_id: int) -> dict | None:
    return conn.execute("SELECT * FROM prompts WHERE id = %s", (prompt_id,)).fetchone()


def get_prompt_by_name(conn: Connection, name: str) -> dict | None:
    return conn.execute("SELECT * FROM prompts WHERE name = %s", (name,)).fetchone()


def list_prompts(conn: Connection) -> list[dict]:
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


def get_latest_version(conn: Connection, prompt_id: int) -> dict | None:
    return conn.execute(
        "SELECT TOP 1 * FROM prompt_versions WHERE prompt_id = %s ORDER BY version DESC",
        (prompt_id,),
    ).fetchone()


def insert_version(
    conn: Connection, prompt_id: int, version: int, template: str,
    model: str | None, notes: str,
) -> int:
    return conn.execute(
        """INSERT INTO prompt_versions (prompt_id, version, template, model, notes)
           OUTPUT INSERTED.id
           VALUES (%s, %s, %s, %s, %s)""",
        (prompt_id, version, template, model, notes),
    ).fetchone()["id"]


def get_version(conn: Connection, prompt_id: int, version: int) -> dict | None:
    return conn.execute(
        "SELECT * FROM prompt_versions WHERE prompt_id = %s AND version = %s",
        (prompt_id, version),
    ).fetchone()


def get_version_by_id(conn: Connection, version_id: int) -> dict | None:
    return conn.execute(
        "SELECT * FROM prompt_versions WHERE id = %s", (version_id,)
    ).fetchone()


def list_versions(conn: Connection, prompt_id: int) -> list[dict]:
    return conn.execute(
        "SELECT * FROM prompt_versions WHERE prompt_id = %s ORDER BY version",
        (prompt_id,),
    ).fetchall()


def insert_test_case(
    conn: Connection, prompt_id: int, name: str, inputs_json: str, checks_json: str
) -> int:
    return conn.execute(
        """INSERT INTO test_cases (prompt_id, name, inputs, checks)
           OUTPUT INSERTED.id
           VALUES (%s, %s, %s, %s)""",
        (prompt_id, name, inputs_json, checks_json),
    ).fetchone()["id"]


def get_test_case(conn: Connection, test_case_id: int) -> dict | None:
    return conn.execute(
        "SELECT * FROM test_cases WHERE id = %s", (test_case_id,)
    ).fetchone()


def list_active_test_cases(conn: Connection, prompt_id: int) -> list[dict]:
    return conn.execute(
        "SELECT * FROM test_cases WHERE prompt_id = %s AND archived = 0 ORDER BY id",
        (prompt_id,),
    ).fetchall()


def archive_test_case(conn: Connection, test_case_id: int) -> None:
    conn.execute("UPDATE test_cases SET archived = 1 WHERE id = %s", (test_case_id,))
