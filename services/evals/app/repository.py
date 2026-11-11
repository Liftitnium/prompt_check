"""SQL for the evals domain. No business rules here, only reads and writes.

No foreign keys point into the prompts service's tables: prompt_version_id and
test_case_id are plain integers, and the template/test case contents are copied
(snapshotted) into these tables when a run is created. See ADR-3. The schema lives
in migrations/*.sql.
"""
from app.db import Connection


def insert_run(
    conn: Connection, prompt_id: int, prompt_version_id: int, version: int,
    template: str, model: str, provider: str, total: int,
) -> int:
    return conn.execute(
        """INSERT INTO eval_runs (prompt_id, prompt_version_id, version, template_snapshot,
                                  model, provider, total)
           OUTPUT INSERTED.id
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (prompt_id, prompt_version_id, version, template, model, provider, total),
    ).fetchone()["id"]


def insert_pending_result(
    conn: Connection, run_id: int, test_case_id: int, name: str,
    inputs_json: str, checks_json: str,
) -> int:
    return conn.execute(
        """INSERT INTO eval_results (run_id, test_case_id, test_case_name,
                                     inputs_snapshot, checks_snapshot)
           OUTPUT INSERTED.id
           VALUES (%s, %s, %s, %s, %s)""",
        (run_id, test_case_id, name, inputs_json, checks_json),
    ).fetchone()["id"]


def get_run(conn: Connection, run_id: int) -> dict | None:
    return conn.execute("SELECT * FROM eval_runs WHERE id = %s", (run_id,)).fetchone()


def list_runs(conn: Connection, prompt_id: int | None = None) -> list[dict]:
    if prompt_id is None:
        return conn.execute("SELECT * FROM eval_runs ORDER BY id DESC").fetchall()
    return conn.execute(
        "SELECT * FROM eval_runs WHERE prompt_id = %s ORDER BY id DESC", (prompt_id,)
    ).fetchall()


def list_results(conn: Connection, run_id: int) -> list[dict]:
    return conn.execute(
        "SELECT * FROM eval_results WHERE run_id = %s ORDER BY id", (run_id,)
    ).fetchall()


def mark_run_running(conn: Connection, run_id: int) -> None:
    conn.execute(
        "UPDATE eval_runs SET status = 'running', started_at = SYSUTCDATETIME() WHERE id = %s",
        (run_id,),
    )


def update_result(conn: Connection, result_id: int, fields: dict) -> None:
    """Save one evaluated test case. Every outcome sets the same eight columns."""
    conn.execute(
        """UPDATE eval_results SET
               status = %s, rendered_prompt = %s, output = %s, check_details = %s,
               error = %s, latency_ms = %s, tokens_in = %s, tokens_out = %s
           WHERE id = %s""",
        (fields["status"], fields["rendered_prompt"], fields["output"], fields["check_details"],
         fields["error"], fields["latency_ms"], fields["tokens_in"], fields["tokens_out"],
         result_id),
    )


def finish_run(conn: Connection, run_id: int) -> None:
    """Count the results and mark the run completed."""
    conn.execute(
        """UPDATE eval_runs SET
               status = 'completed',
               finished_at = SYSUTCDATETIME(),
               passed  = (SELECT COUNT(*) FROM eval_results WHERE run_id = %s AND status = 'pass'),
               failed  = (SELECT COUNT(*) FROM eval_results WHERE run_id = %s AND status = 'fail'),
               errored = (SELECT COUNT(*) FROM eval_results WHERE run_id = %s AND status = 'error')
           WHERE id = %s""",
        (run_id, run_id, run_id, run_id),
    )


def fail_run(conn: Connection, run_id: int, error: str) -> None:
    conn.execute(
        """UPDATE eval_runs SET status = 'failed', error = %s, finished_at = SYSUTCDATETIME()
           WHERE id = %s""",
        (error, run_id),
    )


def fail_unfinished_runs(conn: Connection, error: str) -> int:
    """Mark every pending/running run (and its pending results) as failed. Returns how many runs."""
    conn.execute(
        """UPDATE eval_results SET status = 'error', error = %s
           WHERE status = 'pending'
             AND run_id IN (SELECT id FROM eval_runs WHERE status IN ('pending', 'running'))""",
        (error,),
    )
    return conn.execute(
        """UPDATE eval_runs SET status = 'failed', error = %s, finished_at = SYSUTCDATETIME()
           WHERE status IN ('pending', 'running')""",
        (error,),
    ).rowcount
