-- 001: prompts, their immutable versions, and test cases.
-- Applied once by app/db.py:migrate and recorded in schema_migrations. Never edit this
-- file after it has run anywhere; a schema change is a new numbered file.

CREATE TABLE prompts (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    name        NVARCHAR(200) NOT NULL CONSTRAINT uq_prompts_name UNIQUE,
    description NVARCHAR(MAX) NOT NULL DEFAULT '',
    created_at  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE prompt_versions (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    prompt_id  INT           NOT NULL CONSTRAINT fk_versions_prompt REFERENCES prompts(id),
    version    INT           NOT NULL,
    template   NVARCHAR(MAX) NOT NULL,
    model      NVARCHAR(100) NULL,
    notes      NVARCHAR(MAX) NOT NULL DEFAULT '',
    created_at DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    -- two publishes racing for the same number: the second one fails here
    CONSTRAINT uq_prompt_versions UNIQUE (prompt_id, version)
);

CREATE TABLE test_cases (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    prompt_id  INT           NOT NULL CONSTRAINT fk_test_cases_prompt REFERENCES prompts(id),
    name       NVARCHAR(200) NOT NULL,
    inputs     NVARCHAR(MAX) NOT NULL,
    checks     NVARCHAR(MAX) NOT NULL,
    archived   BIT           NOT NULL DEFAULT 0,
    created_at DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE INDEX ix_test_cases_prompt ON test_cases (prompt_id, archived);
