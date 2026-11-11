-- 001: eval runs and their per-test-case results.
-- No foreign keys point at the prompts service's tables (they live in another
-- database): prompt_version_id and test_case_id are plain integers, and the template
-- and test cases are snapshotted here when a run is created. See ADR-3.
-- Never edit this file after it has run anywhere; a schema change is a new numbered file.

CREATE TABLE eval_runs (
    id                INT IDENTITY(1,1) PRIMARY KEY,
    prompt_id         INT           NOT NULL,
    prompt_version_id INT           NOT NULL,
    version           INT           NOT NULL,
    template_snapshot NVARCHAR(MAX) NOT NULL,
    model             NVARCHAR(100) NOT NULL,
    provider          NVARCHAR(50)  NOT NULL,
    status            NVARCHAR(20)  NOT NULL DEFAULT 'pending'
                      CONSTRAINT ck_eval_runs_status
                      CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    total             INT           NOT NULL DEFAULT 0,
    passed            INT           NOT NULL DEFAULT 0,
    failed            INT           NOT NULL DEFAULT 0,
    errored           INT           NOT NULL DEFAULT 0,
    error             NVARCHAR(MAX) NULL,
    created_at        DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    started_at        DATETIME2     NULL,
    finished_at       DATETIME2     NULL
);

CREATE TABLE eval_results (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    run_id          INT           NOT NULL CONSTRAINT fk_results_run REFERENCES eval_runs(id),
    test_case_id    INT           NOT NULL,
    test_case_name  NVARCHAR(200) NOT NULL,
    inputs_snapshot NVARCHAR(MAX) NOT NULL,
    checks_snapshot NVARCHAR(MAX) NOT NULL,
    status          NVARCHAR(20)  NOT NULL DEFAULT 'pending'
                    CONSTRAINT ck_eval_results_status
                    CHECK (status IN ('pending', 'pass', 'fail', 'error')),
    rendered_prompt NVARCHAR(MAX) NULL,
    output          NVARCHAR(MAX) NULL,
    check_details   NVARCHAR(MAX) NULL,
    error           NVARCHAR(MAX) NULL,
    latency_ms      INT           NULL,
    tokens_in       INT           NULL,
    tokens_out      INT           NULL
);

CREATE INDEX ix_eval_runs_prompt ON eval_runs (prompt_id);
CREATE INDEX ix_eval_results_run ON eval_results (run_id);
