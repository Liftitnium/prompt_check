import asyncio
from types import SimpleNamespace

import pytest

from promptcheck.config import Settings
from promptcheck.evals.llm_client import (
    AnthropicClient, FakeLLMClient, LLMRefusalError, build_llm_client,
)


def test_fake_client_echoes_prompt_and_counts_words():
    response = asyncio.run(FakeLLMClient().complete("Reply in Spanish: hola", "any-model"))
    assert response.text == "Reply in Spanish: hola"
    assert response.tokens_in == response.tokens_out == 4


def test_build_llm_client(tmp_path):
    assert isinstance(build_llm_client(Settings("0.0.0.0", 1, tmp_path, "fake", None)), FakeLLMClient)
    client = build_llm_client(Settings("0.0.0.0", 1, tmp_path, "anthropic", "test-key"))
    assert isinstance(client, AnthropicClient) and client.name == "anthropic"
    with pytest.raises(ValueError, match="unknown LLM_PROVIDER"):
        build_llm_client(Settings("0.0.0.0", 1, tmp_path, "nope", None))


class StubMessages:
    """Stands in for the SDK's client.messages: records the request, returns a canned message."""

    def __init__(self, message):
        self.message = message
        self.request = None

    async def create(self, **kwargs):
        self.request = kwargs
        return self.message


def stub_sdk(content, stop_reason="end_turn", stop_details=None):
    message = SimpleNamespace(
        content=content, stop_reason=stop_reason, stop_details=stop_details,
        usage=SimpleNamespace(input_tokens=12, output_tokens=7),
    )
    return SimpleNamespace(messages=StubMessages(message))


def text(value):
    return SimpleNamespace(type="text", text=value)


def test_anthropic_client_sends_prompt_and_reads_text_and_usage():
    sdk = stub_sdk([SimpleNamespace(type="thinking", thinking=""), text("Hola, "), text("reembolso")])
    response = asyncio.run(AnthropicClient(sdk_client=sdk).complete("Responde: hola", "claude-opus-5"))

    assert response.text == "Hola, reembolso"  # thinking blocks are skipped
    assert (response.tokens_in, response.tokens_out) == (12, 7)
    assert sdk.messages.request == {
        "model": "claude-opus-5",
        "max_tokens": AnthropicClient.MAX_TOKENS,
        "messages": [{"role": "user", "content": "Responde: hola"}],
    }


def test_anthropic_client_turns_refusal_into_error():
    sdk = stub_sdk([], stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"))
    with pytest.raises(LLMRefusalError, match="category: cyber"):
        asyncio.run(AnthropicClient(sdk_client=sdk).complete("x", "claude-opus-5"))


def test_anthropic_client_refusal_without_details():
    sdk = stub_sdk([], stop_reason="refusal")
    with pytest.raises(LLMRefusalError, match="category: None"):
        asyncio.run(AnthropicClient(sdk_client=sdk).complete("x", "claude-opus-5"))
