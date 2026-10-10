"""LLM-as-judge: the one check type that is not a pure function (ADR-5 changed on 2026-10-10).

An `llm_judge` check asks a model whether an output meets a plain-language rubric
("replies politely and in Spanish"). Rule checks stay pure in checks.py; this module
adds the network call and puts both kinds of result back in the test case's order.
"""
from typing import Protocol

from promptcheck.config import Settings
from promptcheck.evals.checks import CheckResult, run_checks
from promptcheck.evals.llm_client import LLMClient

JUDGE_TYPE = "llm_judge"


def judge_prompt(rubric: str, output: str) -> str:
    return (
        "You are grading a reply written by an AI assistant against a rubric.\n\n"
        f"Rubric: {rubric}\n\n"
        f"<reply>\n{output}\n</reply>\n\n"
        "Does the reply meet the rubric? Answer PASS or FAIL on the first line, "
        "then give one short sentence explaining why."
    )


class Judge(Protocol):
    async def judge(self, output: str, rubric: str) -> tuple[bool, str]: ...


class FakeJudge:
    """Deterministic stand-in so demos and tests need no API key: passes any non-empty output."""

    async def judge(self, output: str, rubric: str) -> tuple[bool, str]:
        if output.strip():
            return True, "fake judge: non-empty output passes"
        return False, "fake judge: empty output"


class LLMJudge:
    """Asks a model for a PASS/FAIL verdict.

    Always uses the server's default model (LLM_MODEL), not the prompt version's model,
    so changing the model under test doesn't also change who grades it. Judge tokens are
    not added to the result's token counts, which measure the prompt under test only.
    """

    def __init__(self, llm: LLMClient, model: str):
        self._llm = llm
        self._model = model

    async def judge(self, output: str, rubric: str) -> tuple[bool, str]:
        response = await self._llm.complete(judge_prompt(rubric, output), self._model)
        return parse_verdict(response.text)


def parse_verdict(text: str) -> tuple[bool, str]:
    first, _, rest = text.strip().partition("\n")
    # models sometimes bold or head the verdict ("**PASS**"), so strip markdown first
    verdict = first.strip().strip("*#: ").upper()
    reason = rest.strip() or first.strip()
    if verdict.startswith("PASS"):
        return True, f"judge: {reason}"
    if verdict.startswith("FAIL"):
        return False, f"judge: {reason}"
    # an unclear answer must not count as a pass
    return False, f"judge gave no PASS/FAIL verdict: {first.strip()[:100]!r}"


def build_judge(settings: Settings, llm: LLMClient) -> Judge:
    if settings.llm_provider == "fake":
        return FakeJudge()
    return LLMJudge(llm, settings.llm_model)


async def score_output(output: str, checks: list[dict], judge: Judge | None) -> list[CheckResult]:
    """Rule checks through run_checks, judge checks through the judge, in the checks' order.
    A failing judge call raises, so the caller can mark the case as an error."""
    results = []
    for check in checks:
        if check["type"] != JUDGE_TYPE:
            results.extend(run_checks(output, [check]))
        elif judge is None:
            results.append(CheckResult(JUDGE_TYPE, False, "no judge configured"))
        else:
            passed, detail = await judge.judge(output, check["arg"])
            results.append(CheckResult(JUDGE_TYPE, passed, detail))
    return results
