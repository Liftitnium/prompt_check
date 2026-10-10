import pytest

from promptcheck.errors import InvalidInputError
from promptcheck.prompts.check_specs import validate_checks


def test_valid_checks_are_normalised():
    checks = validate_checks([
        {"type": "contains", "arg": "reembolso"},
        {"type": "valid_json", "arg": "ignored"},
        {"type": "max_length", "arg": 500},
        {"type": "json_has_keys", "arg": ["reply", "language"]},
    ])
    assert checks[1] == {"type": "valid_json"}  # no-arg checks drop their arg
    assert checks[2] == {"type": "max_length", "arg": 500}


@pytest.mark.parametrize("check, message", [
    ({"type": "sounds_nice"}, "unknown check type"),
    ({"type": "contains"}, "needs an arg of type str"),
    ({"type": "contains", "arg": 5}, "needs an arg of type str"),
    ({"type": "max_length", "arg": True}, "needs an arg of type int"),
    ({"type": "max_length", "arg": 0}, "must be positive"),
    ({"type": "regex", "arg": "(unclosed"}, "invalid regex"),
    ({"type": "json_has_keys", "arg": ["ok", 3]}, "list of strings"),
    ({"type": "llm_judge", "arg": "   "}, "needs a rubric"),
])
def test_invalid_checks_are_rejected(check, message):
    with pytest.raises(InvalidInputError, match=message):
        validate_checks([check])


def test_empty_check_list_is_rejected():
    with pytest.raises(InvalidInputError, match="at least one check"):
        validate_checks([])
