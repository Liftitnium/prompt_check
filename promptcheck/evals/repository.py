"""SQL for the evals domain.

No foreign keys point into the prompts tables: prompt_version_id and test_case_id
are plain integers, and the template/test case contents are copied (snapshotted)
into these tables when a run is created. See ADR-3.
"""
import sqlite3
from datetime import UTC, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS eval_runs (
    id                INTEGER PRIMARY KEY,
    prompt_id         INTEGER NOT NULL,
    prompt_version_id INTEGER NOT NULL,
    version           INTEGER NOT NULL,
    template_snapshot TEXT NOT NULL,
    model             TEXT NOT NULL,
    provider          TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    total             INTEGER NOT NULL DEFAULT 0,
    passed            INTEGER NOT NULL DEFAULT 0,
    failed            INTEGER NOT NULL DEFAULT 0,
    errored           INTEGER NOT NULL DEFAULT 0,
    error             TEXT,
    created_at        TEXT NOT NULL,
    started_at        TEXT,
    finished_at       TEXT
);

CREATE TABLE IF NOT EXISTS eval_results (
    id              INTEGER PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES eval_runs(id),
    test_case_id    INTEGER NOT NULL,
    test_case_name  TEXT NOT NULL,
    inputs_snapshot TEXT NOT NULL,
    checks_snapshot TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'pass', 'fail', 'error')),
    rendered_prompt TEXT,
    output          TEXT,
    check_details   TEXT,
    error           TEXT,
    latency_ms      INTEGER,
    tokens_in       INTEGER,
    tokens_out      INTEGER
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_prompt ON eval_runs(prompt_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_run ON eval_results(run_id);
"""


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def insert_run(
    conn: sqlite3.Connection, prompt_id: int, prompt_version_id: int, version: int,
    template: str, model: str, provider: str, total: int,
) -> int:
    cur = conn.execute(
        """INSERT INTO eval_runs (prompt_id, prompt_version_id, version, template_snapshot,
                                  model, provider, total, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (prompt_id, prompt_version_id, version, template, model, provider, total, now_iso()),
    )
    return cur.lastrowid


def insert_pending_result(
    conn: sqlite3.Connection, run_id: int, test_case_id: int, name: str,
    inputs_json: str, checks_json: str,
) -> int:
    cur = conn.execute(
        """INSERT INTO eval_results (run_id, test_case_id, test_case_name,
                                     inputs_snapshot, checks_snapshot)
           VALUES (?, ?, ?, ?, ?)""",
        (run_id, test_case_id, name, inputs_json, checks_json),
    )
    return cur.lastrowid


def get_run(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(conn: sqlite3.Connection, prompt_id: int | None = None) -> list[sqlite3.Row]:
    if prompt_id is None:
        return conn.execute("SELECT * FROM eval_runs ORDER BY id DESC").fetchall()
    return conn.execute(
        "SELECT * FROM eval_runs WHERE prompt_id = ? ORDER BY id DESC", (prompt_id,)
    ).fetchall()


def list_results(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM eval_results WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()


def mark_run_running(conn: sqlite3.Connection, run_id: int) -> None:
    conn.execute(
        "UPDATE eval_runs SET status = 'running', started_at = ? WHERE id = ?",
        (now_iso(), run_id),
    )


def update_result(conn: sqlite3.Connection, result_id: int, fields: dict) -> None:
    columns = ", ".join(f"{name} = ?" for name in fields)  # names come from our code, not users
    conn.execute(
        f"UPDATE eval_results SET {columns} WHERE id = ?", (*fields.values(), result_id)
    )


def finish_run(conn: sqlite3.Connection, run_id: int) -> None:
    """Count the results and mark the run completed."""
    conn.execute(
        """UPDATE eval_runs SET
               status = 'completed',
               finished_at = ?,
               passed  = (SELECT COUNT(*) FROM eval_results WHERE run_id = ? AND status = 'pass'),
               failed  = (SELECT COUNT(*) FROM eval_results WHERE run_id = ? AND status = 'fail'),
               errored = (SELECT COUNT(*) FROM eval_results WHERE run_id = ? AND status = 'error')
           WHERE id = ?""",
        (now_iso(), run_id, run_id, run_id, run_id),
    )


def fail_run(conn: sqlite3.Connection, run_id: int, error: str) -> None:
    conn.execute(
        "UPDATE eval_runs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
        (error, now_iso(), run_id),
    )


def fail_unfinished_runs(conn: sqlite3.Connection, error: str) -> int:
    """Mark every pending/running run (and its pending results) as failed. Returns how many runs."""
    conn.execute(
        """UPDATE eval_results SET status = 'error', error = ?
           WHERE status = 'pending'
             AND run_id IN (SELECT id FROM eval_runs WHERE status IN ('pending', 'running'))""",
        (error,),
    )
    cur = conn.execute(
        """UPDATE eval_runs SET status = 'failed', error = ?, finished_at = ?
           WHERE status IN ('pending', 'running')""",
        (error, now_iso()),
    )
    return cur.rowcount
