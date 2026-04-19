from unittest.mock import MagicMock, patch

import pytest
from ollama import ResponseError

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.providers.cloud_qwen import CloudQwenProvider
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
from ticket_triage_llm.schemas.model_result import ModelResult


class FakeProvider:
    """Minimal fake that satisfies LlmProvider structurally."""

    name: str = "fake"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
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

    @patch("ticket_triage_llm.providers.ollama_qwen.ollama_client.Client")
    def test_generate_returns_model_result(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = '{"category": "billing"}'
        mock_response.prompt_eval_count = 100
        mock_response.eval_count = 50
        mock_client.chat.return_value = mock_response

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

    @patch("ticket_triage_llm.providers.ollama_qwen.ollama_client.Client")
    def test_generate_passes_sampling_params(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.message.content = '{"category": "billing"}'
        mock_response.prompt_eval_count = 10
        mock_response.eval_count = 5
        mock_client.chat.return_value = mock_response

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        provider.generate_structured_ticket("test ticket", "v1")

        call_kwargs = mock_client.chat.call_args
        assert call_kwargs.kwargs["think"] is False
        options = call_kwargs.kwargs["options"]
        assert options["temperature"] == 0.2
        assert options["num_predict"] == 2048
        assert options["top_p"] == 0.9
        assert options["top_k"] == 40
        assert options["repeat_penalty"] == 1.0

    @patch("ticket_triage_llm.providers.ollama_qwen.ollama_client.Client")
    def test_think_defaults_to_false(self, mock_client_cls):
        """Production default: thinking mode must be off unless explicitly enabled."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.message.content = '{"category": "billing"}'
        mock_response.prompt_eval_count = 10
        mock_response.eval_count = 5
        mock_client.chat.return_value = mock_response

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        provider.generate_structured_ticket("test ticket", "v1")

        assert mock_client.chat.call_args.kwargs["think"] is False

    @patch("ticket_triage_llm.providers.ollama_qwen.ollama_client.Client")
    def test_think_true_is_forwarded(self, mock_client_cls):
        """E5 support: think=True must reach the underlying ollama.chat call."""
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.message.content = '{"category": "billing"}'
        mock_response.prompt_eval_count = 10
        mock_response.eval_count = 5
        mock_client.chat.return_value = mock_response

        provider = OllamaQwenProvider(
            model="qwen3.5:9b",
            base_url="http://localhost:11434/v1",
            think=True,
        )
        provider.generate_structured_ticket("test ticket", "v1")

        assert mock_client.chat.call_args.kwargs["think"] is True

    @patch("ticket_triage_llm.providers.ollama_qwen.ollama_client.Client")
    def test_generate_raises_provider_error_on_connection_failure(
        self, mock_client_cls
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.side_effect = ConnectionError("refused")

        provider = OllamaQwenProvider(
            model="qwen3.5:4b", base_url="http://localhost:11434/v1"
        )
        with pytest.raises(ProviderError):
            provider.generate_structured_ticket("test ticket", "v1")

    @patch("ticket_triage_llm.providers.ollama_qwen.ollama_client.Client")
    def test_generate_raises_provider_error_on_response_error(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.chat.side_effect = ResponseError("model not found")

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
