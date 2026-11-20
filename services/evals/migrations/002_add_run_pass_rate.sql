-- 002: store each run's pass rate, so runs can be sorted and filtered by it in SQL.
-- Changes a table that already holds data: existing completed runs are backfilled from
-- their own passed/total counts; every other row stays NULL ("no meaningful pass rate").
-- Runs in one transaction with its schema_migrations row (app/db.py:migrate).

ALTER TABLE eval_runs ADD pass_rate DECIMAL(5, 4) NULL;
GO

-- a separate batch: SQL Server compiles a batch before running it, so the new column
-- is only visible to statements after the GO
UPDATE eval_runs
   SET pass_rate = CAST(passed AS DECIMAL(9, 4)) / total
 WHERE status = 'completed' AND total > 0;
