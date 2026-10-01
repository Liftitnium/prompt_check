import pytest

from promptcheck.evals.templates import MissingVariableError, render


def test_render_fills_every_placeholder():
    assert render("Hi {name}, re: {topic}. Bye {name}", {"name": "Ana", "topic": "refund"}) == \
        "Hi Ana, re: refund. Bye Ana"


def test_render_ignores_extra_inputs():
    assert render("Reply: {message}", {"message": "hola", "unused": "x"}) == "Reply: hola"


def test_render_leaves_literal_json_braces_alone():
    template = 'Answer as {"reply": "..."} for: {message}'
    assert render(template, {"message": "hola"}) == 'Answer as {"reply": "..."} for: hola'


def test_missing_variables_are_all_reported_once():
    with pytest.raises(MissingVariableError) as exc:
        render("{a} {b} {a}", {})
    assert exc.value.missing == ["a", "b"]
    assert "missing input variables: a, b" in str(exc.value)
