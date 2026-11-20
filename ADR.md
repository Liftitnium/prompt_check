# Architecture Decision Records

## 1. Backend framework: FastAPI with the standard-library sqlite3 module
Date: 2026-09-29
Status: Superseded by [7] (SQLite replaced by SQL Server, one database per service)
Context: PromptCheck is a JSON API used by an 8-person AI team, and running an evaluation means calling a slow external LLM API. I need request validation, auto-generated API docs, and a small dependency footprint to stay under ~12 packages.
Decision: Use FastAPI (served by uvicorn) with Pydantic models for validation, and Python's built-in sqlite3 module with hand-written SQL instead of an ORM. Eval runs execute as in-process FastAPI `BackgroundTasks` (asyncio, capped by a semaphore), so `POST /runs` returns 202 immediately and everything stays in one process. The web UI is plain HTML/CSS/JS in `promptcheck/static/`, served by the same process and calling the same JSON API.
Alternatives considered: Flask was rejected because I would have to add separate libraries for validation and API docs, which FastAPI provides built in. Django was rejected because its admin, templates, and ORM are features this API does not need. SQLAlchemy was rejected because the schema is small (5 tables) and raw SQL keeps every query visible and explainable. Celery + Redis for runs was rejected because the assignment rules out brokers and job runners (§1c), and ~50 runs/week doesn't need them. A React/Vite frontend was rejected because it would add a Node build step and a second dependency manifest, which the one-manifest rule (§1a) doesn't allow.
Consequences: The /docs page documents the API for free and validation errors are automatic. The UI needs no build step, but hand-written DOM code will get harder to maintain if the UI grows a lot more screens. Without an ORM I write migrations and row-to-object mapping by hand, which will cost more if the schema grows. An in-process run dies with the process, so startup marks interrupted runs as failed.

## 2. Splitting prompts and evals into independently modularizable domains
Date: 2026-09-30
Status: Decided
Context: PromptCheck has two responsibilities: managing prompts (versions, test cases) and running/scoring evaluations against an LLM. Assignment 2 will split the monolith into services, so the boundary has to exist in the code now even though everything runs in one process.
Decision: Each domain is its own package (`promptcheck/prompts`, `promptcheck/evals`) with its own router, service, repository and schema SQL. Evals may only get prompt data through the `PromptsGateway` protocol in `evals/gateway.py`, whose one method `get_version_for_run(version_id)` is implemented today by calling `prompts.service` in-process, and dependencies only point one way (evals → prompts). The check vocabulary (`prompts/check_specs.py`) lives in prompts so test cases can be validated on creation without importing evals.
Alternatives considered: A single shared `models.py`/`repository.py` for all tables was rejected because evals code would end up joining prompts tables directly, and those joins would all break when the database is split. Putting check validation in evals was rejected because it would make prompts import evals, creating a two-way dependency.
Consequences: Turning evals into its own service means swapping `InProcessPromptsGateway` for an HTTP implementation that calls a `GET /versions/{id}/for-run` endpoint. The cost is a little indirection now, plus keeping `check_specs.py` and the evals check implementations in sync (enforced by a test).

## 3. Eval tables snapshot prompt data instead of using cross-domain foreign keys
Date: 2026-09-30
Status: Decided
Context: An eval run needs the template and test cases that were current when it started, but prompts keep getting new versions and test cases get archived. Evals must also be able to move to its own database when the domains become separate services.
Decision: Foreign keys only exist inside a domain (prompt_versions → prompts, eval_results → eval_runs). Evals stores prompt_version_id and test_case_id as plain integers, and at run creation copies the template into eval_runs.template_snapshot and each test case's inputs/checks into a pending eval_results row.
Alternatives considered: Real foreign keys from eval_results to test_cases and eval_runs to prompt_versions, reading the template through a join at display time. Rejected because archiving or changing a test case would silently change what an old run appears to have tested, and cross-domain foreign keys would have to be removed anyway before the databases can be split.
Consequences: Every run is reproducible and self-contained, and the evals tables can move to another database unchanged. The cost is duplicated data (the template and test cases are stored again per run) and no database-level guarantee that a referenced version still exists.

## 4. Testing approach: business logic against a real SQLite file, with the LLM faked
Date: 2026-10-08
Status: Decided
Context: The brief needs ≥70% coverage on core business logic. In PromptCheck the risky logic is version numbering, check validation, scoring, run status changes and the regression verdict, and the one external dependency (the LLM API) is slow, costs money and gives different answers each time.
Decision: Most tests call `prompts/service.py`, `evals/runner.py`, `checks.py` and `compare.py` directly against a fresh SQLite file in pytest's `tmp_path`, with `FakeLLMClient` or small stub clients (failing, concurrency-tracking) standing in for the LLM and stub judges standing in for `llm_judge` checks; `AnthropicClient` is tested with a stub SDK object, and a few `TestClient` tests check HTTP status codes and the startup seed. Coverage is measured with `pytest --cov=promptcheck` (120 tests, 99%).
Alternatives considered: Mocking the database with fake repositories was rejected because the SQL (UNIQUE constraints, snapshots, the empty-table seed guard) is part of what can break, and SQLite in a temp folder is just as fast. Calling the real Claude API in tests was rejected because it needs a key, costs money and would make results flaky.
Consequences: Tests run in under a second with no network and catch real SQL mistakes. Left thinner: no test hits the real Anthropic API, and there are no load tests or multi-process write tests, so SDK retry behaviour and SQLite's single writer under heavy use are trusted rather than proven.

## 5. Not building authentication or user accounts
Date: 2026-10-10
Status: Decided
Context: PromptCheck is used by one 8-person AI team on the company's internal network, and every endpoint can create prompts or start runs that spend Anthropic API credit. Login would mean a users table, password hashing or SSO, sessions, and permission checks on every route. This entry replaces my original ADR-5 (2026-10-03, not building LLM-as-judge scoring): on 2026-10-10 I reversed that decision and added an optional `llm_judge` check, because rule checks can't express qualities like language or tone, so authentication became the feature I deliberately left out.
Decision: No authentication and no user accounts: anyone who can reach the server can use every endpoint. Access control is left to the network the container runs on.
Alternatives considered: API keys or a login page using FastAPI's security helpers, with a `users` table and a `team_id` on prompts. Rejected because for 8 trusted colleagues it adds a third concern that isn't one of the two domains, more tables and more tests, while protecting against nobody in the current setup.
Consequences: The app stays two domains and starts with no setup. The cost is that anyone on the network can edit prompts or run up API costs, so exposing it outside the internal network, or adding a second team, means adding auth plus a `team_id` column on prompts first.

## 6. The split: the seam stays where ADR-2 put it, and only run creation crosses it
Date: 2026-11-20
Status: Decided
Context: Assignment 2 splits the monolith into two services, each with its own database. ADR-2 had already drawn the seam inside the monolith: evals could only reach prompt data through the `PromptsGateway` protocol and its one method, `get_version_for_run(version_id)`.
Decision: The seam did not move. `prompts` and `evals` are separate services in `services/<name>`, each with its own requirements, Dockerfile, migrations and database. One flow crosses the seam on the server side. `POST /runs` on evals calls `GET /versions/{version_id}/for-run` on prompts through `HttpPromptsGateway` (httpx, with a 2-second timeout from `PROMPTS_TIMEOUT_S`) and snapshots the template and test cases it returns (ADR-3). The UI calls each service directly for its own domain. If prompts is down or slow, `POST /runs` returns 503 ("the prompts service is unavailable; try again later") and stores nothing. Evals keeps serving existing runs, results and comparisons from its own snapshots. Prompts validates check types and evals implements them. A test in evals reads prompts' `CHECK_SPECS` and fails if the two sides drift apart.
Alternatives considered:
- Making the cross-seam call from the UI, which would fetch the version from prompts and post it to evals. Rejected because evals would have to trust a template sent by the browser, and the brief requires at least one server-side flow.
- Caching versions in evals, or retrying inside the request, when prompts is down. Rejected because a run must use the current version and test cases, and a stale cache could evaluate archived ones. A retry inside the request would also keep the user waiting past the timeout. Failing fast with a clear 503 is simpler, and the user can retry.
- Moving check validation into evals. Rejected for the same reason as in ADR-2: prompts would have to call evals on every test-case write, creating a two-way dependency.
Consequences: ADR-2 held. The only change in evals was swapping `InProcessPromptsGateway` for `HttpPromptsGateway`, and prompts only had to expose the endpoint the gateway already assumed. Creating a run now depends on prompts being up, but reading results does not. A function call became a wire contract, so its shape is documented in both OpenAPI files and checked by the cross-seam integration test in CI (ADR-9). On Azure, the bare app name did not resolve inside the Container Apps environment, so `PROMPTS_URL` is prompts' public HTTPS address, set by the deploy workflow. That adds one hop through the ingress.

## 7. Data and migrations: one database per service, numbered SQL files applied at startup
Date: 2026-11-20
Status: Decided
Context: Assignment 1 kept all five tables in one SQLite file and created the schema on first boot. Assignment 2 needs one database per service on SQL Server (Azure SQL serverless in production), and once a database holds data its schema has to change in place.
Decision:
- **Ownership.** The prompts database owns `prompts`, `prompt_versions` and `test_cases`. The evals database owns `eval_runs` and `eval_results`. Each service logs in with its own user (`prompts_app`, `evals_app`), which can only reach its own database.
- **Moving the data.** No data was copied from the A1 SQLite file, because it only held demo data. That data ships as `seed.json` and is loaded into an empty prompts database on first boot (`SEED_DEMO`). Evals starts empty.
- **Integrity lost at the seam.** The split dropped no foreign key, because since ADR-3 the cross-domain references (`eval_runs.prompt_version_id`, `eval_results.test_case_id`) have been plain integers. What was lost is any database guarantee that a referenced version still exists. This is compensated in three ways: runs snapshot their template and test cases when they are created, so a finished run never needs prompts again; versions are immutable and never deleted; and test cases are archived, never deleted.
- **Migrations.** Each service has numbered files in `services/<name>/migrations/`. My own runner, `app/db.py:migrate`, applies them at startup in name order, records each in `schema_migrations`, and runs each file in one transaction together with its `schema_migrations` row (`GO` splits batches). Applied files are never edited. `002_add_run_pass_rate.sql` adds `eval_runs.pass_rate` and backfills it from each completed run's `passed`/`total`. This is the migration that changed a table already holding data on Azure.
- **Recovery plan for a bad migration (forward-only, no down-migrations):**
  1. **The migration fails.** The file's transaction rolls back with its `schema_migrations` row, and the new container never starts listening. In single-revision mode, Container Apps keeps the previous revision serving, and the deploy's `/health` check fails the run. The fix is a corrected new file, since a failed file was never recorded.
  2. **The migration succeeds but is wrong.** Fix it forward with a new numbered migration.
  3. **It destroyed or corrupted data.** Use Azure SQL point-in-time restore (7 days of backups) into a new database, then point the `database-url` secret at it.
- **Local SQL Server version.** Locally and in CI I use SQL Server 2025 rather than the brief's 2022-latest, because the 2022 image crashed under Rosetta on my Apple Silicon machine. Azure SQL is versionless, and the T-SQL used (`IDENTITY`, `DATETIME2`, `OUTPUT INSERTED`, `NVARCHAR(MAX)`) behaves the same on both.
Alternatives considered:
- Alembic. Rejected because it brings SQLAlchemy, which ADR-1 already rejected, plus two dependencies per service, for two migrations. My runner is about 40 lines and has tests, including one that a failed file leaves nothing behind.
- One database with two schemas. Rejected by the brief, and it would let evals join prompts' tables again.
- Down-migrations. Not written, because point-in-time restore covers the case where reversing a change would actually matter, which is losing data.
Consequences: The schema history is visible in plain SQL files and replays identically locally, in CI and on Azure. Migrations run at startup, which is safe only because each app runs at most one replica (ADR-8). With two replicas, both could try to apply the same file. A data-changing migration has to be written to finish inside one transaction on a database that may have just resumed from pause. Restoring from a backup loses everything written after the restore point.
