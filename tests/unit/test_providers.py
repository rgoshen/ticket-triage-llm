from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.providers.cloud_qwen import CloudQwenProvider
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.schemas.model_result import ModelResult


class FakeProvider:
    """Minimal fake that satisfies LlmProvider structurally."""

    name: str = "fake"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        return ModelResult(
            raw_output='{"category": "billing"}',
            model="fake-model",
            latency_ms=10.0,
            tokens_input=5,
            tokens_output=10,
            tokens_total=15,
        )


class TestLlmProviderProtocol:
    def test_fake_satisfies_protocol(self):
        provider: LlmProvider = FakeProvider()
        assert provider.name == "fake"

    def test_fake_returns_model_result(self):
        provider: LlmProvider = FakeProvider()
        result = provider.generate_structured_ticket("test ticket", "v1")
        assert isinstance(result, ModelResult)
        assert result.raw_output == '{"category": "billing"}'

    def test_protocol_is_structural(self):
        """LlmProvider is a Protocol -- no inheritance required."""
        assert LlmProvider not in FakeProvider.__mro__
        provider: LlmProvider = FakeProvider()
        assert provider.name == "fake"


class TestOllamaQwenProviderName:
    def test_has_name(self):
        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        assert provider.name == "ollama:qwen3.5:4b"

    def test_model_parameterization(self):
        p2b = OllamaQwenProvider(
            model="qwen3.5:2b", base_url="http://localhost:11434/v1"
        )
        p9b = OllamaQwenProvider(
            model="qwen3.5:9b", base_url="http://localhost:11434/v1"
        )
        assert p2b.name == "ollama:qwen3.5:2b"
        assert p9b.name == "ollama:qwen3.5:9b"


class TestOllamaQwenProviderConcrete:
    def test_constructor_accepts_model_and_base_url(self):
        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        assert provider.name == "ollama:qwen3.5:4b"

    @patch("ticket_triage_llm.providers.ollama_qwen.OpenAI")
    def test_generate_returns_model_result(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = '{"category": "billing"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        mock_client.chat.completions.create.return_value = mock_response

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        result = provider.generate_structured_ticket("test ticket", "v1")

        assert isinstance(result, ModelResult)
        assert result.raw_output == '{"category": "billing"}'
        assert result.model == "qwen3.5:4b"
        assert result.tokens_input == 100
        assert result.tokens_output == 50
        assert result.tokens_total == 150
        assert result.latency_ms > 0

    @patch("ticket_triage_llm.providers.ollama_qwen.OpenAI")
    def test_generate_passes_sampling_params(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = '{"category": "billing"}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        provider.generate_structured_ticket("test ticket", "v1")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.2
        assert call_kwargs.kwargs["max_tokens"] == 2048
        extra = call_kwargs.kwargs["extra_body"]
        assert extra["top_p"] == 0.9
        assert extra["top_k"] == 40
        assert extra["repetition_penalty"] == 1.0

    @patch("ticket_triage_llm.providers.ollama_qwen.OpenAI")
    def test_generate_raises_provider_error_on_connection_failure(
        self, mock_openai_cls
    ):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        with pytest.raises(ProviderError):
            provider.generate_structured_ticket("test ticket", "v1")


class TestCloudQwenProviderStub:
    def test_has_name(self):
        provider = CloudQwenProvider()
        assert provider.name == "cloud:qwen"

    def test_generate_raises_not_implemented(self):
        provider = CloudQwenProvider()
        with pytest.raises(NotImplementedError):
            provider.generate_structured_ticket("test", "v1")
