"""Check implementations: each one is a pure function (output, arg) -> CheckResult.

The set of check types is defined by prompts/check_specs.py (the contract);
this module implements every rule type listed there; `llm_judge` needs a model call,
so it lives in judge.py. A test keeps the contract and the implementations in sync.
"""
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CheckResult:
    type: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


def check_contains(output: str, arg: str) -> tuple[bool, str]:
    found = arg.lower() in output.lower()
    return found, f"{'found' if found else 'missing'} {arg!r}"


def check_not_contains(output: str, arg: str) -> tuple[bool, str]:
    found = arg.lower() in output.lower()
    return not found, f"{'unexpectedly found' if found else 'absent'} {arg!r}"


def check_equals(output: str, arg: str) -> tuple[bool, str]:
    equal = output.strip() == arg.strip()
    return equal, "exact match" if equal else f"expected {arg!r}"


def check_regex(output: str, arg: str) -> tuple[bool, str]:
    match = re.search(arg, output)
    return match is not None, f"{'matched' if match else 'no match for'} /{arg}/"


def check_max_length(output: str, arg: int) -> tuple[bool, str]:
    length = len(output)
    return length <= arg, f"{length} chars (max {arg})"


def check_valid_json(output: str, arg: None = None) -> tuple[bool, str]:
    try:
        json.loads(output)
    except json.JSONDecodeError as e:
        return False, f"invalid JSON: {e.msg}"
    return True, "valid JSON"


def check_json_has_keys(output: str, arg: list[str]) -> tuple[bool, str]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return False, "not JSON"
    if not isinstance(data, dict):
        return False, "JSON is not an object"
    missing = [key for key in arg if key not in data]
    return not missing, f"missing keys {missing}" if missing else "all keys present"


# the registry: check type -> function. Adding a check = one function + one line here.
CHECKS: dict[str, Callable[[str, object], tuple[bool, str]]] = {
    "contains": check_contains,
    "not_contains": check_not_contains,
    "equals": check_equals,
    "regex": check_regex,
    "max_length": check_max_length,
    "valid_json": check_valid_json,
    "json_has_keys": check_json_has_keys,
}


def run_checks(output: str, checks: list[dict]) -> list[CheckResult]:
    results = []
    for check in checks:
        fn = CHECKS.get(check["type"])
        if fn is None:
            # can happen if an old snapshot uses a check type that was later removed
            results.append(CheckResult(check["type"], False, "unknown check type"))
            continue
        passed, detail = fn(output, check.get("arg"))
        results.append(CheckResult(check["type"], passed, detail))
    return results
