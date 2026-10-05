"""The LLM boundary. Everything else in evals depends on the LLMClient protocol,
never on a specific provider, so tests and demos run without an API key."""
from dataclasses import dataclass
from typing import Protocol

import anthropic

from promptcheck.config import Settings


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int


class LLMClient(Protocol):
    name: str

    async def complete(self, prompt: str, model: str) -> LLMResponse: ...


class LLMRefusalError(Exception):
    """The model declined to answer (stop_reason == 'refusal')."""


class FakeLLMClient:
    """Deterministic stand-in: replies with the prompt itself.

    Because the output is the rendered prompt, changing a template visibly changes
    what the checks see, so regressions between versions show up in demos and tests.
    """
    name = "fake"

    async def complete(self, prompt: str, model: str) -> LLMResponse:
        words = len(prompt.split())
        return LLMResponse(text=prompt, tokens_in=words, tokens_out=words)


class AnthropicClient:
    """Calls the Claude Messages API through the official SDK.

    Retries are the SDK's job: it retries connection errors, 408, 409, 429 and 5xx
    with exponential backoff (and honours retry-after), up to MAX_RETRIES times.
    No server-side model fallback on refusal: falling back would silently test a
    different model than the prompt version specifies, so a refusal is an error.
    """
    name = "anthropic"
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 120.0
    MAX_TOKENS = 16000

    def __init__(self, api_key: str | None = None, sdk_client=None):
        # api_key=None lets the SDK find credentials itself (ANTHROPIC_API_KEY, `ant auth login`)
        self._client = sdk_client or anthropic.AsyncAnthropic(
            api_key=api_key, max_retries=self.MAX_RETRIES, timeout=self.TIMEOUT_SECONDS
        )

    async def complete(self, prompt: str, model: str) -> LLMResponse:
        message = await self._client.messages.create(
            model=model,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        if message.stop_reason == "refusal":
            category = message.stop_details.category if message.stop_details else None
            raise LLMRefusalError(f"model refused to answer (category: {category})")
        # the response can also hold thinking blocks; only text blocks are the answer
        text = "".join(block.text for block in message.content if block.type == "text")
        return LLMResponse(text, message.usage.input_tokens, message.usage.output_tokens)


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        return FakeLLMClient()
    if settings.llm_provider == "anthropic":
        return AnthropicClient(api_key=settings.llm_api_key)
    raise ValueError(
        f"unknown LLM_PROVIDER {settings.llm_provider!r}; use 'fake' or 'anthropic'"
    )
