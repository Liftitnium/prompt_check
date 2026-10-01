"""The seam between the evals and prompts domains.

Evals depends only on the PromptsGateway protocol. Today the implementation calls
the prompts service in-process; after the split (Assignment 2) an HTTP
implementation replaces it and nothing else in evals changes.
"""
from contextlib import closing
from pathlib import Path
from typing import Protocol

from promptcheck.db import get_connection
from promptcheck.prompts import service as prompts_service


class PromptsGateway(Protocol):
    def get_version_for_run(self, version_id: int) -> dict:
        """Return {id, prompt_id, version, template, model, test_cases: [...]},
        or raise NotFoundError."""
        ...


class InProcessPromptsGateway:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def get_version_for_run(self, version_id: int) -> dict:
        # its own connection, as a separate prompts service would have its own database
        with closing(get_connection(self.db_path)) as conn:
            return prompts_service.get_version_for_run(conn, version_id)
