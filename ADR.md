# Architecture Decision Records

## 1. Backend framework: FastAPI with the standard-library sqlite3 module
Date: 2026-09-29
Status: Decided
Context: PromptCheck is a JSON API used by an 8-person AI team, and running an evaluation means calling a slow external LLM API. I need request validation, auto-generated API docs, and a small dependency footprint to stay under ~12 packages.
Decision: Use FastAPI (served by uvicorn) with Pydantic models for validation, and Python's built-in sqlite3 module with hand-written SQL instead of an ORM.
Alternatives considered: Flask was rejected because I would have to add separate libraries for validation and API docs, which FastAPI provides built in. Django was rejected because its admin, templates, and ORM are features this API does not need. SQLAlchemy was rejected because the schema is small (5 tables) and raw SQL keeps every query visible and explainable.
Consequences: The /docs page gives a usable UI for free and validation errors are automatic. Without an ORM I write migrations and row-to-object mapping by hand, which will cost more if the schema grows.

## 2. Splitting prompts and evals into independently modularizable domains
Date: 2026-09-30
Status: Decided
Context: PromptCheck has two responsibilities: managing prompts (versions, test cases) and running/scoring evaluations against an LLM. Assignment 2 will split the monolith into services, so the boundary has to exist in the code now even though everything runs in one process.
Decision: Each domain is its own package (`promptcheck/prompts`, `promptcheck/evals`) with its own router, service, repository and schema SQL. Evals may only get prompt data through one function, `prompts.service.get_version_for_run(version_id)`, and dependencies only point one way (evals → prompts). The check vocabulary (`prompts/check_specs.py`) lives in prompts so test cases can be validated on creation without importing evals.
Alternatives considered: A single shared `models.py`/`repository.py` for all tables was rejected because evals code would end up joining prompts tables directly, and those joins would all break when the database is split. Putting check validation in evals was rejected because it would make prompts import evals, creating a two-way dependency.
Consequences: Turning evals into its own service means replacing one function call with an HTTP call to a `GET /versions/{id}/for-run` endpoint. The cost is a little indirection now, plus keeping `check_specs.py` and the evals check implementations in sync (enforced by a test).

## 3. Eval tables snapshot prompt data instead of using cross-domain foreign keys
Date: 2026-09-30
Status: Decided
Context: An eval run needs the template and test cases that were current when it started, but prompts keep getting new versions and test cases get archived. Evals must also be able to move to its own database when the domains become separate services.
Decision: Foreign keys only exist inside a domain (prompt_versions → prompts, eval_results → eval_runs). Evals stores prompt_version_id and test_case_id as plain integers, and at run creation copies the template into eval_runs.template_snapshot and each test case's inputs/checks into a pending eval_results row.
Alternatives considered: Real foreign keys from eval_results to test_cases and eval_runs to prompt_versions, reading the template through a join at display time. Rejected because archiving or changing a test case would silently change what an old run appears to have tested, and cross-domain foreign keys would have to be removed anyway before the databases can be split.
Consequences: Every run is reproducible and self-contained, and the evals tables can move to another database unchanged. The cost is duplicated data (the template and test cases are stored again per run) and no database-level guarantee that a referenced version still exists.
