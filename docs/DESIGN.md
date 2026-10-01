# PromptCheck: System Design

## 1. Requirements

### Stakeholder
An 8-person AI team at a Spanish e-commerce startup. Their customer-support assistant runs on ~20 prompts that engineers change weekly. Prompt changes break behaviour silently (wrong language, invalid JSON, missing refund policy), and nobody notices until customers do.

### Functional requirements
| # | Requirement | Domain |
|---|---|---|
| F1 | Create prompts and publish **immutable** versions (a change = a new version) | prompts |
| F2 | See a line-by-line diff between two versions of a prompt | prompts |
| F3 | Attach test cases to a prompt: input variables + one or more checks | prompts |
| F4 | Run a prompt version against all its active test cases through an LLM | evals |
| F5 | Score each output with deterministic checks (contains, regex, valid JSON, ...) | evals |
| F6 | Compare two runs: which cases **regressed**, which got **fixed**, pass-rate and latency deltas, and a ship / don't-ship verdict | evals |
| F7 | Work with no API key (fake LLM) and with a real provider via env vars | evals |
| F8 | A dashboard page to browse prompts, trigger runs, and view comparisons | UI |

### Non-functional requirements (assumed load)
- **Users:** 8 engineers, ~20 prompts × ~30 test cases each.
- **Volume:** ~50 runs/week → ~1,500 LLM calls/week. Tiny: SQLite is more than enough.
- **Latency:** CRUD endpoints < 100 ms. A run is bounded by the LLM (~1-3 s per call), so runs are **asynchronous**: the API answers immediately and the client polls.
- **Reliability:** one failing LLM call must not fail the whole run. Transient API errors (429/5xx) are retried.
- **Cost:** concurrency is capped so a 30-case run doesn't hit provider rate limits.

### Constraints (from the assignment)
Single process / single container, SQLite at `$DATA_DIR/promptcheck.db`, all config via env vars, binds `0.0.0.0`, no brokers/Celery/cron, ~12 packages max, starts in seconds with no manual setup, deadline 2026-10-04.

## 2. High-level design

```
                    ┌──────────────────────────── one uvicorn process ────────────────────────────┐
 Browser ──HTTP──►  │  FastAPI app (main.py)                                                      │
 (dashboard,        │   ├── /static  dashboard.html + app.js                                      │
  /docs)            │   ├── prompts/router.py ──► prompts/service.py ──► prompts/repository.py ──┐ │
                    │   │                               ▲                                        │ │
                    │   │                               │ PromptsGateway (the seam)              │ │
                    │   │                               │                                        ▼ │
                    │   └── evals/router.py ──► evals/runner.py ──► evals/repository.py ──► SQLite │
                    │                             │    │                              promptcheck.db│
                    │                   checks.py │    │ llm_client.py                             │
                    │                  (pure fns) │    ├── FakeLLMClient (default)                 │
                    │                  compare.py │    └── AnthropicClient ──HTTPS──► LLM API      │
                    └──────────────────────────────────────────────────────────────────────────────┘
```

### Layers inside each domain
- **router.py**: HTTP only. Parse the request, call the service, map errors to status codes.
- **service.py / runner.py**: business logic. No HTTP, no SQL. **This is what the tests target.**
- **repository.py**: SQL only. Takes a connection, returns plain dicts/dataclasses.
- **schemas.py**: Pydantic request/response models.

### The seam between domains
`evals` never imports `prompts.repository` or queries prompts tables. It depends on one interface:

```python
class PromptsGateway(Protocol):
    def get_version_for_run(self, version_id: int) -> VersionForRun: ...
    # VersionForRun = prompt_id, version number, template, model, active test cases
```

Today the implementation is an in-process call into `prompts.service`. In Assignment 2, when evals becomes its own service, it becomes an HTTP call to the prompts service. Nothing else in `evals` changes.

## 3. Deep dive

### 3.1 Data model

```
prompts domain                                   evals domain
──────────────                                   ────────────
prompts                                          eval_runs
  id PK                                            id PK
  name UNIQUE                                      prompt_id          (plain int, no FK)
  description                                      prompt_version_id  (plain int, no FK)
  created_at                                       version            (snapshot)
     │1                                            template_snapshot  (snapshot)
     ├──< prompt_versions                          model, provider
     │     id PK                                   status  pending|running|completed|failed
     │     prompt_id FK → prompts.id               total, passed, failed, errored
     │     version  (UNIQUE with prompt_id)        created_at, started_at, finished_at, error
     │     template, model, notes, created_at        │1
     │                                               └──< eval_results
     └──< test_cases                                      id PK
           id PK                                          run_id FK → eval_runs.id
           prompt_id FK → prompts.id                      test_case_id   (plain int, no FK)
           name                                           test_case_name, inputs_snapshot (JSON)
           inputs  (JSON: {"message": "..."})             checks_snapshot (JSON)
           checks  (JSON: [{"type":"contains",...}])      rendered_prompt, output
           archived (0/1), created_at                     status  pass|fail|error
                                                          check_details (JSON), error
                                                          latency_ms, tokens_in, tokens_out
```

**Key decision (ADR-3):** foreign keys exist *inside* a domain, never *across* domains. At run creation, evals **snapshots** the template and each test case into its own tables.
- ✅ Old runs stay reproducible even after test cases are edited or archived.
- ✅ The databases can be split later without breaking constraints.
- ❌ Duplicated data (a template is stored again per run). At ~50 runs/week that's kilobytes.

Test cases belong to the **prompt**, not to a version. That's what makes comparison possible: v3 and v4 are run against the same test set.

Test cases are **archived, not deleted**, so history keeps making sense.

SQLite runs in **WAL mode**, so the dashboard can read while a background run is writing results.

### 3.2 Templates
Templates use `{variable}` placeholders: `Reply in Spanish to: {message}`. `render(template, inputs)` extracts the variables with a regex and raises `MissingVariableError` if an input is missing. The test case's result is then `error`, not a crash.

### 3.3 Checks (strategy pattern + registry)
Each check is a pure function `(output: str, arg) -> CheckResult(passed, detail)`, registered in a dict:

| type | arg | passes when |
|---|---|---|
| `contains` / `not_contains` | string | substring present / absent (case-insensitive) |
| `equals` | string | trimmed output equals the value |
| `regex` | pattern | `re.search` matches |
| `max_length` | int | `len(output) <= n` |
| `valid_json` | none | `json.loads` succeeds |
| `json_has_keys` | list | output is a JSON object containing all the keys |

A test case passes only if **all** its checks pass. Adding a new check = one function + one registry entry. Check definitions are validated when a test case is created, so unknown types are rejected with a 422 error.

### 3.4 LLM client
```python
class LLMClient(Protocol):
    async def complete(self, prompt: str, model: str) -> LLMResponse  # text, tokens_in, tokens_out
```
- **FakeLLMClient** (default, `LLM_PROVIDER=fake`): deterministic, no network. It echoes the rendered prompt, so template changes visibly change the outputs and checks behave meaningfully in the demo.
- **AnthropicClient** (`LLM_PROVIDER=anthropic`, `LLM_API_KEY`, `LLM_MODEL`): uses `httpx.AsyncClient` with a 30 s timeout. **Retries 429/5xx up to 3 times with exponential backoff** (0.5 s, 1 s, 2 s). A 4xx error is not retried.
- The client is picked once at startup by `build_llm_client(settings)`.

### 3.5 Run lifecycle (asynchronous, in-process)
```
POST /runs {prompt_version_id}
  1. gateway.get_version_for_run()            → 404 if the version doesn't exist
  2. insert eval_runs row, status=pending      (template snapshot)
     + one pending eval_results row per test case (inputs/checks snapshot)
  3. BackgroundTasks.add_task(execute_run, id)
  4. return 202 {run_id, status: "pending"}

execute_run(run_id):                          (runs after the response is sent)
  status=running
  asyncio.gather over test cases, limited by Semaphore(LLM_CONCURRENCY=4)
     each: render → llm.complete → run checks → insert eval_results row
     any exception → result status=error; the rest of the run continues
  compute totals → status=completed (or failed if something unexpected broke)

GET /runs/{id}  → the client polls until status is completed or failed
```
**Crash recovery:** in-process tasks die with the process. At startup, `lifespan` marks every `pending`/`running` run as `failed` with the error "interrupted by restart", so no run stays stuck forever.

Why not Celery/Redis: the assignment forbids them, and at ~50 runs/week an in-process task is enough. That makes a good ADR.

### 3.6 Comparison
`compare(base_run, candidate_run)` is a pure function over two lists of results, matched by `test_case_id`:

| base | candidate | category |
|---|---|---|
| pass | fail/error | **regressed** |
| fail/error | pass | **fixed** |
| pass | pass | still passing |
| fail | fail | still failing |
| missing | present | new |
| present | missing | removed |

It returns the categories plus the pass-rate delta, average and p95 latency delta, and token delta. **Verdict:** `ship` if there are 0 regressions and the candidate's pass rate ≥ the base's, otherwise `block`. Both runs must belong to the same prompt and be completed, otherwise 422.

### 3.7 API
| Method | Path | Notes |
|---|---|---|
| GET | `/health` | runs a DB query |
| POST / GET | `/prompts` | create / list (with latest version and last run pass rate) |
| GET | `/prompts/{id}` | details |
| POST / GET | `/prompts/{id}/versions` | publish / list; the version number is assigned automatically |
| GET | `/prompts/{id}/versions/{a}/diff/{b}` | unified diff (`difflib`) |
| POST / GET | `/prompts/{id}/test-cases` | create (checks validated) / list active |
| DELETE | `/test-cases/{id}` | archive |
| GET | `/checks` | available check types and their args |
| POST | `/runs` | 202 + run id |
| GET | `/runs?prompt_id=` | list |
| GET | `/runs/{id}` | run + results |
| GET | `/runs/compare?base=&candidate=` | comparison report |
| GET | `/` | dashboard |

### 3.8 Error handling
Domain errors (`NotFoundError`, `ValidationError`, `ConflictError`) are raised in services and turned into 404/422/409 in **one** exception handler in `main.py`. Services therefore never know about HTTP.

### 3.9 Configuration
`HOST`, `PORT`, `DATA_DIR`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_CONCURRENCY`, `SEED_DEMO` (when true, loads a demo prompt with 2 versions and 6 test cases at startup if the DB is empty, so a grader sees a regression immediately).

## 4. Scale and reliability
- **Current scale:** a single process and SQLite easily handle 8 users. WAL mode handles reads during background writes.
- **What breaks first:** (1) a long run holding the only process while the event loop is busy with blocking sqlite writes; (2) runs lost on restart; (3) SQLite's single writer if many runs happen at once.
- **Monitoring (now):** `/health` checks the DB; each run records status, error, and per-case latency.
- **Assignment 2 path:** split along the `PromptsGateway` seam into a prompts service and an evals service, each with its own DB; move runs to a real queue once brokers are allowed.

## 5. Trade-offs
| Decision | Chosen | Rejected | Why |
|---|---|---|---|
| Framework | FastAPI | Flask, Django | validation + docs + async built in (ADR-1) |
| DB access | raw `sqlite3` | SQLAlchemy | 5 tables, SQL stays visible and explainable, one less dependency |
| Domain coupling | gateway interface + snapshots, no cross-domain FKs | shared tables / joins | splittable later (ADR-2, ADR-3) |
| Run execution | BackgroundTasks + asyncio semaphore | synchronous request; Celery | sync blocks for 30-90 s; Celery isn't allowed |
| Scoring | deterministic rule checks | LLM-as-judge | reproducible, free, testable; judge scoring is a candidate for ADR-5 |
| Auth | none (internal tool) | API keys / login | 8 trusted users on an internal network; also a candidate for ADR-5 |
| Frontend | one static page, vanilla JS | React/Jinja | no build step, no extra dependencies |

## 6. What to revisit as it grows
- More than ~10 concurrent runs → a real job queue and worker processes.
- Multiple teams → auth plus a `team_id` column on prompts.
- Fuzzy quality ("is this reply polite?") → an optional LLM-as-judge check type.
- Test sets drifting apart from versions → pin a test-set snapshot per version.
