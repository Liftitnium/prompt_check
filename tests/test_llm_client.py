import asyncio

import pytest

from promptcheck.config import Settings
from promptcheck.evals.llm_client import FakeLLMClient, build_llm_client


def test_fake_client_echoes_prompt_and_counts_words():
    response = asyncio.run(FakeLLMClient().complete("Reply in Spanish: hola", "any-model"))
    assert response.text == "Reply in Spanish: hola"
    assert response.tokens_in == response.tokens_out == 4


def test_build_llm_client(tmp_path):
    assert isinstance(build_llm_client(Settings("0.0.0.0", 1, tmp_path, "fake", None)), FakeLLMClient)
    with pytest.raises(ValueError, match="unknown LLM_PROVIDER"):
        build_llm_client(Settings("0.0.0.0", 1, tmp_path, "nope", None))
