# PromptCheck

Regression testing for LLM prompts. A team saves each version of a prompt together with a set of test cases, runs every version through an LLM, and sees exactly which test cases regressed before shipping a prompt change.

**Stakeholder:** an 8-person AI team at a Spanish e-commerce startup whose support assistant runs on ~20 prompts that change weekly. Changes break behaviour silently (wrong language, invalid JSON, missing refund policy); PromptCheck catches that before customers do.

## Run it

There are two ways to run it. Both start the same single process with the same command, `python app.py`.

### Directly on your machine

Tested on Python 3.14, the same version as the container image (needs 3.10+ for the `X | None` type syntax).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### In Docker

The `Dockerfile` is the course template with its four `TODO` lines filled in: `python:3.14-slim`, install from `requirements.txt`, copy `app.py` and `promptcheck/`, run `python app.py`.

```bash
docker build -t promptcheck .
docker run -p 8000:8000 -v promptcheck-data:/data promptcheck
# another port:      docker run -e PORT=9000 -p 9000:9000 -v promptcheck-data:/data promptcheck
# real Claude API:   docker run -e LLM_PROVIDER=anthropic -e LLM_API_KEY=sk-ant-... -p 8000:8000 -v promptcheck-data:/data promptcheck
```

Inside the container `DATA_DIR` is `/data`, so the database lives on the named volume and survives the container being removed and recreated.

### Once it is running

- Web UI: http://localhost:8000/ (manifest of prompts → prompt page → runs → gate with a SHIP/HOLD verdict)
- Interactive API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

No setup step is needed. On startup the app creates any missing tables (`CREATE TABLE IF NOT EXISTS`, never `DROP`) and, if there are no prompts yet, loads the demo data from [`promptcheck/prompts/seed.json`](promptcheck/prompts/seed.json). Booting again changes nothing, because the seed is guarded on the prompts table being empty.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port |
| `HOST` | `0.0.0.0` | Bind address (all interfaces, so it works inside a container) |
| `DATA_DIR` | `./data` | Directory holding the SQLite file |
| `LLM_PROVIDER` | `fake` | `fake` (deterministic, no API key needed) or `anthropic` |
| `LLM_API_KEY` | none | Anthropic API key for `LLM_PROVIDER=anthropic`; if unset, the SDK falls back to `ANTHROPIC_API_KEY` |
| `LLM_MODEL` | `claude-opus-5` | Model used when a prompt version doesn't name one (e.g. `claude-haiku-4-5` for cheaper runs) |
| `LLM_CONCURRENCY` | `4` | Max LLM calls in flight during one run |
| `SEED_DEMO` | `true` | Load the demo prompt from `seed.json` on first boot; `false` starts with an empty database |

**SQLite path:** `$DATA_DIR/promptcheck.db`: `./data/promptcheck.db` when run directly, `/data/promptcheck.db` in the container. The database is never committed; it is always built from the schema plus `seed.json`.

## Tests and coverage

```bash
pytest --cov=promptcheck --cov-report=term-missing
```

Current result: 120 tests passed, 99% coverage.

## Container contract evidence (§7)

Output of the course checker, `./container/run.sh /path/to/this/repo`, run on 2026-10-08:

```
=== SDD Assignment 1 contract check ===
Repository: /Users/rajinasrallah/code/devops_assignment

==> Repository shape
  PASS  one Dockerfile, one manifest (requirements.txt)

==> Build from a clean context, no build args
  PASS  image built
  PASS  image size 61 MB

==> Start on PORT=8000 and reach it from the host
  PASS  HTTP 307 from http://localhost:8000/

==> SQLite file under DATA_DIR
  PASS  found in /data: promptcheck.db 

==> Data persists, and a second boot does not re-seed
  PASS  volume at /data persists
  PASS  row counts unchanged across restart: eval_results=0 eval_runs=0 prompt_versions=2 prompts=1 test_cases=3 

==> PORT override is honoured (not hardcoded)
  PASS  HTTP 307 from http://localhost:9123/

=== ALL CHECKS PASSED ===
Paste this output into your README as the §7 evidence.
```

## Project layout

```
app.py                    entry point: python app.py
requirements.txt          the one dependency manifest
Dockerfile                course template, four TODOs filled in
promptcheck/
  config.py               Settings loaded from environment variables
  db.py                   SQLite connection, schema init, per-request connection
  errors.py               domain errors mapped to 404 / 409 / 422
  main.py                 create_app(): startup, error handler, routers
  prompts/                domain 1: prompts, immutable versions, test cases
    router.py             HTTP endpoints
    service.py            business rules (+ get_version_for_run, the seam used by evals)
    repository.py         SQL and table definitions
    check_specs.py        allowed check types and their arguments
    schemas.py            request/response models
    seed.py, seed.json    demo data loaded on first boot when there are no prompts
  static/                 web UI: index.html, app.css, app.js, self-hosted fonts (no build step)
  evals/                  domain 2: evaluation runs and scoring
    router.py             HTTP endpoints (POST /runs returns 202, runs in background)
    runner.py             create_run, evaluate_case, execute_run, startup recovery
    checks.py             check functions + CHECKS registry
    judge.py              llm_judge checks: Judge protocol, LLMJudge, FakeJudge, score_output
    templates.py          render {variables} into a template
    llm_client.py         LLMClient protocol, FakeLLMClient, AnthropicClient (official SDK)
    compare.py            compare two runs: regressions, fixes, deltas, ship/block verdict
    gateway.py            PromptsGateway: the only way evals reads prompt data
    repository.py         SQL and table definitions
    schemas.py            request/response models
tests/                    pytest suite
docs/DESIGN.md            system design
ADR.md                    architecture decision records
AI_USAGE.md               AI usage log
```

## API

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Database-backed health check |
| POST / GET | `/prompts` | Create a prompt / list prompts |
| GET | `/prompts/{id}` | Get one prompt |
| POST / GET | `/prompts/{id}/versions` | Publish the next version / list versions |
| GET | `/prompts/{id}/versions/{n}` | Get one version and its template variables |
| GET | `/prompts/{id}/versions/{a}/diff/{b}` | Line diff between two versions |
| POST / GET | `/prompts/{id}/test-cases` | Add a test case / list active test cases |
| DELETE | `/test-cases/{id}` | Archive a test case |
| GET | `/checks` | Available check types |
| POST | `/runs` | Start a run for `{"prompt_version_id": n}`; returns 202 immediately |
| GET | `/runs?prompt_id=` | List runs, newest first |
| GET | `/runs/compare?base=&candidate=` | Regressions, fixes, pass-rate/latency/token deltas and a `ship`/`block` verdict |
| GET | `/runs/{id}` | Run status, pass rate and per-test-case results |
| POST | `/runs/{id}/rescore` | Re-score a completed run's stored outputs with the current checks, as a new run (no new outputs; only `llm_judge` checks call the judge; 201) |

### Example: the seeded demo

The demo prompt `refund-reply` has two versions. v2 is an English rewrite that drops the refund policy, so two of its three test cases regress:

```bash
curl -X POST localhost:8000/runs -H 'content-type: application/json' -d '{"prompt_version_id": 1}'   # run 1
curl -X POST localhost:8000/runs -H 'content-type: application/json' -d '{"prompt_version_id": 2}'   # run 2
curl localhost:8000/runs/1               # poll until "status" is "completed" (pass_rate 1.0)
curl "localhost:8000/runs/compare?base=1&candidate=2"
# -> {"verdict": "block", "summary": {"regressed": 2, "still_passing": 1, ...}}
```

Fixed a check? Test cases can't be edited, so archive the old one and add a new one with the same inputs. Then `POST /runs/1/rescore` re-applies the current checks to run 1's stored outputs and returns a new run, without generating new outputs. Outputs are matched by inputs; a test case with new inputs is skipped, because scoring it needs a real run.

### Example: your own prompt

```bash
curl -X POST localhost:8000/prompts -H 'content-type: application/json' \
  -d '{"name": "order-status"}'            # -> {"id": 2, ...}

curl -X POST localhost:8000/prompts/2/versions -H 'content-type: application/json' \
  -d '{"template": "Responde en español al cliente sobre su pedido: {message}"}'

curl -X POST localhost:8000/prompts/2/test-cases -H 'content-type: application/json' \
  -d '{"name": "spanish reply", "inputs": {"message": "¿dónde está mi pedido?"},
       "checks": [{"type": "contains", "arg": "español"}, {"type": "max_length", "arg": 600}]}'

curl localhost:8000/prompts/2/versions   # the new version's "id" is what POST /runs takes
```

## Using the real Claude API

```bash
LLM_PROVIDER=anthropic LLM_API_KEY=sk-ant-... python app.py
```

The SDK retries rate limits (429) and server errors (5xx) up to 3 times with exponential backoff. A refused request is recorded as an `error` result for that test case; the rest of the run continues.
