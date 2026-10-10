# Architecture Decision Records

## 1. Backend framework: FastAPI with the standard-library sqlite3 module
Date: 2026-09-29
Status: Decided
Context: PromptCheck is a JSON API used by an 8-person AI team, and running an evaluation means calling a slow external LLM API. I need request validation, auto-generated API docs, and a small dependency footprint to stay under ~12 packages.
Decision: Use FastAPI (served by uvicorn) with Pydantic models for validation, and Python's built-in sqlite3 module with hand-written SQL instead of an ORM. Eval runs execute as in-process FastAPI `BackgroundTasks` (asyncio, capped by a semaphore), so `POST /runs` returns 202 immediately and everything stays in one process.
Alternatives considered: Flask was rejected because I would have to add separate libraries for validation and API docs, which FastAPI provides built in. Django was rejected because its admin, templates, and ORM are features this API does not need. SQLAlchemy was rejected because the schema is small (5 tables) and raw SQL keeps every query visible and explainable. Celery + Redis for runs was rejected because the assignment rules out brokers and job runners (§1c), and ~50 runs/week doesn't need them.
Consequences: The /docs page gives a usable UI for free and validation errors are automatic. Without an ORM I write migrations and row-to-object mapping by hand, which will cost more if the schema grows. An in-process run dies with the process, so startup marks interrupted runs as failed.

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
Decision: Most tests call `prompts/service.py`, `evals/runner.py`, `checks.py` and `compare.py` directly against a fresh SQLite file in pytest's `tmp_path`, with `FakeLLMClient` or small stub clients (failing, concurrency-tracking) standing in for the LLM; `AnthropicClient` is tested with a stub SDK object, and a few `TestClient` tests check HTTP status codes and the startup seed. Coverage is measured with `pytest --cov=promptcheck` (97 tests, 99%).
Alternatives considered: Mocking the database with fake repositories was rejected because the SQL (UNIQUE constraints, snapshots, the empty-table seed guard) is part of what can break, and SQLite in a temp folder is just as fast. Calling the real Claude API in tests was rejected because it needs a key, costs money and would make results flaky.
Consequences: Tests run in under a second with no network and catch real SQL mistakes. Left thinner: no test hits the real Anthropic API, and there are no load tests or multi-process write tests, so SDK retry behaviour and SQLite's single writer under heavy use are trusted rather than proven.

