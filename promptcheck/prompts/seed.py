"""Demo data loaded on first boot. It ships as a readable JSON file, never as a
prebuilt .db, so it works on an empty volume, a bind mount or an Azure file share."""
import json
import sqlite3
from pathlib import Path

from promptcheck.prompts import service

SEED_FILE = Path(__file__).with_name("seed.json")


def load_seed(conn: sqlite3.Connection, seed_file: Path = SEED_FILE) -> bool:
    """Create the demo prompts only when there are no prompts yet.

    The empty-table guard makes this idempotent: a second boot, or a database a
    user has already filled, is left untouched. Returns True if it seeded.
    """
    if service.list_prompts(conn):
        return False
    data = json.loads(seed_file.read_text(encoding="utf-8"))
    for p in data["prompts"]:
        # through the service, so seed data gets the same validation as API input
        prompt = service.create_prompt(conn, p["name"], p.get("description", ""))
        for v in p["versions"]:
            service.publish_version(conn, prompt["id"], v["template"], v.get("model"), v.get("notes", ""))
        for tc in p["test_cases"]:
            service.add_test_case(conn, prompt["id"], tc["name"], tc["inputs"], tc["checks"])
    return True
