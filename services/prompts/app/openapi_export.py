"""Write this service's OpenAPI document to openapi.yaml (the committed copy).

    cd services/<name> && python -m app.openapi_export

tests/test_openapi.py fails when the committed file no longer matches the code,
so after changing a route or schema, run this and commit the result.
"""
from pathlib import Path

import yaml

from app.config import Settings
from app.main import create_app

OPENAPI_FILE = Path(__file__).resolve().parent.parent / "openapi.yaml"
# the live document reports the deployed git sha; the committed one a fixed version
DOCUMENT_VERSION = "2.0.0"


def build() -> dict:
    # building the document never connects: the database is only opened at startup
    app = create_app(Settings(database_url="mssql://unused:unused@unused/unused", version=DOCUMENT_VERSION))
    return app.openapi()


def render() -> str:
    return yaml.safe_dump(build(), sort_keys=False, allow_unicode=True)


if __name__ == "__main__":
    OPENAPI_FILE.write_text(render())
    print(f"wrote {OPENAPI_FILE}")
