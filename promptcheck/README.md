# PromptCheck

Regression testing for LLM prompts. Save prompt versions with test cases, run them against an LLM, and see which cases regressed between versions before shipping a prompt change.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000/docs for the interactive API, or check http://localhost:8000/health.

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | HTTP port |
| `HOST` | `0.0.0.0` | Bind address |
| `DATA_DIR` | `./data` | Directory holding the SQLite file `promptcheck.db` |
| `LLM_PROVIDER` | `fake` | `fake` (no API key needed) or a real provider |
| `LLM_API_KEY` | none | Required only for a real provider |

The SQLite database lives at `$DATA_DIR/promptcheck.db` and is created automatically on startup.

## Tests and coverage

```bash
pytest --cov=promptcheck --cov-report=term-missing
```
