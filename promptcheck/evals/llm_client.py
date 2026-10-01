"""The LLM boundary. Everything else in evals depends on the LLMClient protocol,
never on a specific provider, so tests and demos run without an API key."""
from dataclasses import dataclass
from typing import Protocol

from promptcheck.config import Settings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int


class LLMClient(Protocol):
    name: str

    async def complete(self, prompt: str, model: str) -> LLMResponse: ...


class FakeLLMClient:
    """Deterministic stand-in: replies with the prompt itself.

    Because the output is the rendered prompt, changing a template visibly changes
    what the checks see, so regressions between versions show up in demos and tests.
    """
    name = "fake"

    async def complete(self, prompt: str, model: str) -> LLMResponse:
        words = len(prompt.split())
        return LLMResponse(text=prompt, tokens_in=words, tokens_out=words)


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FakeLLMClient()
    raise ValueError(f"unknown LLM_PROVIDER {settings.llm_provider!r}; use 'fake'")
