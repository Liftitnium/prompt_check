"""The committed openapi.yaml must match the code and be a valid OpenAPI document."""
import yaml
from openapi_spec_validator import validate

from app.openapi_export import OPENAPI_FILE, build


def test_committed_openapi_matches_the_code():
    committed = yaml.safe_load(OPENAPI_FILE.read_text())
    assert committed == build(), "openapi.yaml is stale: run `python -m app.openapi_export`"


def test_openapi_document_is_valid():
    validate(yaml.safe_load(OPENAPI_FILE.read_text()))
