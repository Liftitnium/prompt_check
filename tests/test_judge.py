import asyncio

import pytest

from promptcheck.config import Settings
from promptcheck.evals.judge import FakeJudge, LLMJudge, build_judge, parse_verdict, score_output
from promptcheck.evals.llm_client import FakeLLMClient, LLMResponse


class ScriptedLLM:
    """Replies with a fixed text and remembers what it was asked."""
    name = "scripted"

    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def complete(self, prompt, model):
        self.calls.append((prompt, model))
        return LLMResponse(self.reply, 10, 2)


@pytest.mark.parametrize("text, passed", [
    ("PASS\nThe reply offers a refund.", True),
    ("**PASS**\nPolite and in Spanish.", True),
    ("pass - looks fine", True),
    ("FAIL\nIt never mentions a refund.", False),
    ("FAILED: wrong language", False),
    ("I think it is probably fine", False),  # no clear verdict never counts as a pass
    ("", False),
])
def test_parse_verdict(text, passed):
    result, detail = parse_verdict(text)
    assert result is passed
    assert detail


def test_parse_verdict_keeps_the_reason():
    assert parse_verdict("FAIL\nIt is in English.") == (False, "judge: It is in English.")


def test_llm_judge_sends_rubric_and_output_to_the_default_model():
    llm = ScriptedLLM("PASS\nok")
    passed, _ = asyncio.run(LLMJudge(llm, "judge-model").judge("Hola, le reembolsamos.", "offers a refund"))
    assert passed is True
    [(prompt, model)] = llm.calls
    assert model == "judge-model"
    assert "Rubric: offers a refund" in prompt
    assert "<reply>\nHola, le reembolsamos.\n</reply>" in prompt


def test_fake_judge_passes_non_empty_output_only():
    assert asyncio.run(FakeJudge().judge("hola", "anything"))[0] is True
    assert asyncio.run(FakeJudge().judge("  ", "anything"))[0] is False


def test_build_judge_matches_the_provider(tmp_path):
    fake = Settings("0.0.0.0", 8000, tmp_path, "fake", None)
    assert isinstance(build_judge(fake, FakeLLMClient()), FakeJudge)
    real = Settings("0.0.0.0", 8000, tmp_path, "anthropic", "key", llm_model="claude-x")
    judge = build_judge(real, ScriptedLLM("PASS"))
    assert isinstance(judge, LLMJudge)


def test_score_output_keeps_check_order_and_mixes_rule_and_judge_checks():
    checks = [
        {"type": "llm_judge", "arg": "is polite"},
        {"type": "contains", "arg": "hola"},
    ]
    results = asyncio.run(score_output("Hola", checks, LLMJudge(ScriptedLLM("FAIL\nrude"), "m")))
    assert [(r.type, r.passed) for r in results] == [("llm_judge", False), ("contains", True)]


def test_score_output_without_a_judge_fails_judge_checks():
    [result] = asyncio.run(score_output("Hola", [{"type": "llm_judge", "arg": "is polite"}], None))
    assert (result.passed, result.detail) == (False, "no judge configured")
