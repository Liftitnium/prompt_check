-- One database and one login per service. Run as sa by the one-off db-init container
-- (docker compose) on every `up`, so every statement is guarded: running it again
-- changes nothing, except re-applying the passwords from .env.
-- sqlcmd fills $(PROMPTS_DB_PASSWORD) and $(EVALS_DB_PASSWORD) from the environment.
-- Tables are not created here: each service applies its own migrations at startup.
SET NOCOUNT ON;

IF DB_ID(N'promptcheck_prompts') IS NULL CREATE DATABASE promptcheck_prompts;
IF DB_ID(N'promptcheck_evals') IS NULL CREATE DATABASE promptcheck_evals;
GO

-- readers never wait for writers (the UI polls a run while its results are written).
-- Only switched once: the ALTER needs the database to itself.
IF EXISTS (SELECT 1 FROM sys.databases WHERE name = N'promptcheck_prompts' AND is_read_committed_snapshot_on = 0)
    ALTER DATABASE promptcheck_prompts SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
IF EXISTS (SELECT 1 FROM sys.databases WHERE name = N'promptcheck_evals' AND is_read_committed_snapshot_on = 0)
    ALTER DATABASE promptcheck_evals SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO

-- logins: created once, password re-applied on every run so .env stays the source of truth
DECLARE @sql NVARCHAR(MAX);

IF SUSER_ID(N'prompts_app') IS NULL
    SET @sql = N'CREATE LOGIN prompts_app WITH PASSWORD = ' + QUOTENAME(N'$(PROMPTS_DB_PASSWORD)', N'''')
             + N', DEFAULT_DATABASE = promptcheck_prompts';
ELSE
    SET @sql = N'ALTER LOGIN prompts_app WITH PASSWORD = ' + QUOTENAME(N'$(PROMPTS_DB_PASSWORD)', N'''');
EXEC (@sql);

IF SUSER_ID(N'evals_app') IS NULL
    SET @sql = N'CREATE LOGIN evals_app WITH PASSWORD = ' + QUOTENAME(N'$(EVALS_DB_PASSWORD)', N'''')
             + N', DEFAULT_DATABASE = promptcheck_evals';
ELSE
    SET @sql = N'ALTER LOGIN evals_app WITH PASSWORD = ' + QUOTENAME(N'$(EVALS_DB_PASSWORD)', N'''');
EXEC (@sql);
GO

-- each login is a user in its own database only. db_owner there lets the service run
-- its own migrations; it has no user at all in the other service's database.
USE promptcheck_prompts;
IF USER_ID(N'prompts_app') IS NULL CREATE USER prompts_app FOR LOGIN prompts_app;
IF IS_ROLEMEMBER(N'db_owner', N'prompts_app') = 0 ALTER ROLE db_owner ADD MEMBER prompts_app;
GO

USE promptcheck_evals;
IF USER_ID(N'evals_app') IS NULL CREATE USER evals_app FOR LOGIN evals_app;
IF IS_ROLEMEMBER(N'db_owner', N'evals_app') = 0 ALTER ROLE db_owner ADD MEMBER evals_app;
GO

PRINT 'db-init: databases and logins are in place';
