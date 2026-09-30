"""Business rules for prompts, versions and test cases. No HTTP, no raw SQL."""
import difflib
import json
import re
import sqlite3

from promptcheck.errors import ConflictError, InvalidInputError, NotFoundError
from promptcheck.prompts import repository as repo
from promptcheck.prompts.check_specs import validate_checks

VARIABLE_PATTERN = re.compile(r"\{(\w+)\}")


def template_variables(template: str) -> list[str]:
    """'Hi {name}, re: {topic}' -> ['name', 'topic'] (unique, in order of appearance)."""
    return list(dict.fromkeys(VARIABLE_PATTERN.findall(template)))


# ---------- prompts ----------

def create_prompt(conn: sqlite3.Connection, name: str, description: str = "") -> dict:
    name = name.strip()
    if not name:
        raise InvalidInputError("prompt name cannot be empty")
    if repo.get_prompt_by_name(conn, name):
        raise ConflictError(f"a prompt named {name!r} already exists")
    prompt_id = repo.insert_prompt(conn, name, description)
    return get_prompt(conn, prompt_id)


def get_prompt(conn: sqlite3.Connection, prompt_id: int) -> dict:
    row = repo.get_prompt(conn, prompt_id)
    if row is None:
        raise NotFoundError(f"prompt {prompt_id} not found")
    return dict(row)


def list_prompts(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in repo.list_prompts(conn)]


# ---------- versions ----------

def publish_version(
    conn: sqlite3.Connection, prompt_id: int, template: str,
    model: str | None = None, notes: str = "",
) -> dict:
    """Versions are immutable: every change creates version N+1."""
    get_prompt(conn, prompt_id)  # 404 if the prompt doesn't exist
    if not template.strip():
        raise InvalidInputError("template cannot be empty")

    latest = repo.get_latest_version(conn, prompt_id)
    if latest and latest["template"] == template and latest["model"] == model:
        raise ConflictError(f"identical to v{latest['version']}; nothing to publish")

    next_version = latest["version"] + 1 if latest else 1
    try:
        repo.insert_version(conn, prompt_id, next_version, template, model, notes)
    except sqlite3.IntegrityError as e:
        # two publishes raced for the same number; UNIQUE(prompt_id, version) caught it
        raise ConflictError("another version was published at the same time; retry") from e
    return get_version(conn, prompt_id, next_version)


def get_version(conn: sqlite3.Connection, prompt_id: int, version: int) -> dict:
    row = repo.get_version(conn, prompt_id, version)
    if row is None:
        raise NotFoundError(f"prompt {prompt_id} has no version {version}")
    return _version_to_dict(row)


def list_versions(conn: sqlite3.Connection, prompt_id: int) -> list[dict]:
    get_prompt(conn, prompt_id)
    return [_version_to_dict(row) for row in repo.list_versions(conn, prompt_id)]


def diff_versions(conn: sqlite3.Connection, prompt_id: int, a: int, b: int) -> dict:
    old = get_version(conn, prompt_id, a)
    new = get_version(conn, prompt_id, b)
    lines = list(difflib.unified_diff(
        old["template"].splitlines(), new["template"].splitlines(),
        fromfile=f"v{a}", tofile=f"v{b}", lineterm="",
    ))
    # skip the '---'/'+++' file headers when counting changed lines
    body = [line for line in lines if not line.startswith(("---", "+++"))]
    return {
        "from_version": a,
        "to_version": b,
        "added": sum(1 for line in body if line.startswith("+")),
        "removed": sum(1 for line in body if line.startswith("-")),
        "model_changed": old["model"] != new["model"],
        "diff": lines,
    }


def _version_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["variables"] = template_variables(data["template"])
    return data


# ---------- test cases ----------

def add_test_case(
    conn: sqlite3.Connection, prompt_id: int, name: str, inputs: dict, checks: list[dict]
) -> dict:
    get_prompt(conn, prompt_id)
    if not name.strip():
        raise InvalidInputError("test case name cannot be empty")
    if not all(isinstance(v, str) for v in inputs.values()):
        raise InvalidInputError("test case inputs must be strings")
    clean_checks = validate_checks(checks)
    test_case_id = repo.insert_test_case(
        conn, prompt_id, name.strip(), json.dumps(inputs), json.dumps(clean_checks)
    )
    return _test_case_to_dict(repo.get_test_case(conn, test_case_id))


def list_test_cases(conn: sqlite3.Connection, prompt_id: int) -> list[dict]:
    get_prompt(conn, prompt_id)
    return [_test_case_to_dict(row) for row in repo.list_active_test_cases(conn, prompt_id)]


def archive_test_case(conn: sqlite3.Connection, test_case_id: int) -> None:
    """Archive instead of delete, so old eval runs that used this case still make sense."""
    if repo.get_test_case(conn, test_case_id) is None:
        raise NotFoundError(f"test case {test_case_id} not found")
    repo.archive_test_case(conn, test_case_id)


def _test_case_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["inputs"] = json.loads(data["inputs"])
    data["checks"] = json.loads(data["checks"])
    data["archived"] = bool(data["archived"])
    return data


# ---------- the seam: what the evals domain is allowed to ask for ----------

def get_version_for_run(conn: sqlite3.Connection, version_id: int) -> dict:
    """Everything evals needs to run one version, in one call.

    This is the only function the evals domain uses. When the domains become
    separate services, this becomes an HTTP endpoint and evals calls it remotely.
    """
    row = repo.get_version_by_id(conn, version_id)
    if row is None:
        raise NotFoundError(f"prompt version {version_id} not found")
    version = _version_to_dict(row)
    version["test_cases"] = list_test_cases(conn, version["prompt_id"])
    return version
