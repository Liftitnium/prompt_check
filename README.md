# PromptCheck

Regression testing for LLM prompts. A team saves each version of a prompt together with a set of test cases, runs every version through an LLM, and sees exactly which test cases regressed before shipping a prompt change.

**Stakeholder:** an 8-person AI team at a Spanish e-commerce startup whose support assistant runs on ~20 prompts that change weekly. Changes break behaviour silently (wrong language, invalid JSON, missing refund policy); PromptCheck catches that before customers do.

## Run it

Tested on Python 3.14 (needs 3.10+ for the `X | None` type syntax).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

- Interactive API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

No setup step is needed: the SQLite database and its tables are created automatically on startup.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port |
| `HOST` | `0.0.0.0` | Bind address (all interfaces, so it works inside a container) |
| `DATA_DIR` | `./data` | Directory holding the SQLite file |
| `LLM_PROVIDER` | `fake` | `fake` (deterministic, no API key needed) or `anthropic` |
| `LLM_API_KEY` | none | Required only when `LLM_PROVIDER=anthropic` |

**SQLite path:** `$DATA_DIR/promptcheck.db` (default `./data/promptcheck.db`).

## Tests and coverage

```bash
pytest --cov=promptcheck --cov-report=term-missing
```

Current result: 35 tests passed, 99% coverage.

## Project layout

```
app.py                    entry point: python app.py
requirements.txt          the one dependency manifest
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
tests/                    pytest suite
docs/DESIGN.md            system design
ADR.md                    architecture decision records
AI_USAGE.md               AI usage log
```

## API (prompts domain)

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

### Example

```bash
curl -X POST localhost:8000/prompts -H 'content-type: application/json' \
  -d '{"name": "refund-reply"}'

curl -X POST localhost:8000/prompts/1/versions -H 'content-type: application/json' \
  -d '{"template": "Reply in Spanish to this customer: {message}"}'

curl -X POST localhost:8000/prompts/1/test-cases -H 'content-type: application/json' \
  -d '{"name": "spanish refund", "inputs": {"message": "quiero devolver mis zapatillas"},
       "checks": [{"type": "contains", "arg": "reembolso"}, {"type": "max_length", "arg": 600}]}'
```
