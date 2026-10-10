"""The check vocabulary: which check types exist and what argument each takes.

The prompts domain owns this contract so it can validate test cases on creation.
The evals domain implements the actual check functions against it.
"""
import re

from promptcheck.errors import InvalidInputError

# check type -> expected type of "arg" (None means the check takes no arg)
CHECK_SPECS: dict[str, type | None] = {
    "contains": str,
    "not_contains": str,
    "equals": str,
    "regex": str,
    "max_length": int,
    "valid_json": None,
    "json_has_keys": list,
    "llm_judge": str,  # arg is a plain-language rubric; scored by a model (evals/judge.py)
}


def validate_checks(checks: list[dict]) -> list[dict]:
    if not checks:
        raise InvalidInputError("a test case needs at least one check")
    return [_validate_one(check) for check in checks]


def _validate_one(check: dict) -> dict:
    check_type = check.get("type")
    if check_type not in CHECK_SPECS:
        raise InvalidInputError(
            f"unknown check type {check_type!r}; allowed: {sorted(CHECK_SPECS)}"
        )
    expected = CHECK_SPECS[check_type]
    arg = check.get("arg")

    if expected is None:
        return {"type": check_type}
    # bool is a subclass of int in Python, so reject it explicitly
    if not isinstance(arg, expected) or isinstance(arg, bool):
        raise InvalidInputError(f"check {check_type!r} needs an arg of type {expected.__name__}")
    if check_type == "regex":
        try:
            re.compile(arg)
        except re.error as e:
            raise InvalidInputError(f"invalid regex {arg!r}: {e}") from e
    if check_type == "max_length" and arg <= 0:
        raise InvalidInputError("max_length must be positive")
    if check_type == "json_has_keys" and not all(isinstance(k, str) for k in arg):
        raise InvalidInputError("json_has_keys needs a list of strings")
    if check_type == "llm_judge" and not arg.strip():
        raise InvalidInputError("llm_judge needs a rubric")
    return {"type": check_type, "arg": arg}
