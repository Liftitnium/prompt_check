import pytest

from promptcheck.evals.checks import CHECKS, run_checks
from promptcheck.evals.judge import JUDGE_TYPE
from promptcheck.prompts.check_specs import CHECK_SPECS


def test_every_specified_check_type_is_implemented():
    # keeps the prompts-side contract and the evals-side implementation in sync
    assert set(CHECKS) | {JUDGE_TYPE} == set(CHECK_SPECS)


@pytest.mark.parametrize("check, output, expected", [
    ({"type": "contains", "arg": "Reembolso"}, "Tramitamos su reembolso hoy", True),
    ({"type": "contains", "arg": "reembolso"}, "Gracias por escribir", False),
    ({"type": "not_contains", "arg": "estafa"}, "Lamentamos las molestias", True),
    ({"type": "not_contains", "arg": "estafa"}, "No es una estafa", False),
    ({"type": "equals", "arg": "OK"}, "  OK \n", True),
    ({"type": "equals", "arg": "OK"}, "OK!", False),
    ({"type": "regex", "arg": r"pedido \d{4}"}, "Su pedido 4412 sale hoy", True),
    ({"type": "regex", "arg": r"pedido \d{4}"}, "Su pedido sale hoy", False),
    ({"type": "max_length", "arg": 5}, "12345", True),
    ({"type": "max_length", "arg": 5}, "123456", False),
    ({"type": "valid_json"}, '{"reply": "hola"}', True),
    ({"type": "valid_json"}, "reply: hola", False),
    ({"type": "json_has_keys", "arg": ["reply", "language"]}, '{"reply": "hola", "language": "es"}', True),
    ({"type": "json_has_keys", "arg": ["reply", "language"]}, '{"reply": "hola"}', False),
    ({"type": "json_has_keys", "arg": ["reply"]}, '["reply"]', False),
    ({"type": "json_has_keys", "arg": ["reply"]}, "not json", False),
])
def test_each_check(check, output, expected):
    [result] = run_checks(output, [check])
    assert result.passed is expected
    assert result.type == check["type"]
    assert result.detail  # every result explains itself


def test_unknown_check_type_fails_instead_of_crashing():
    [result] = run_checks("anything", [{"type": "removed_check"}])
    assert result.passed is False
    assert result.detail == "unknown check type"


def test_detail_messages_are_specific():
    [length] = run_checks("123456", [{"type": "max_length", "arg": 5}])
    assert length.detail == "6 chars (max 5)"
    [keys] = run_checks('{"a": 1}', [{"type": "json_has_keys", "arg": ["a", "b"]}])
    assert keys.detail == "missing keys ['b']"
