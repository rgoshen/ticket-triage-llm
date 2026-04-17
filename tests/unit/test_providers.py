import pytest

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.providers.cloud_qwen import CloudQwenProvider
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


class TestOllamaQwenProviderStub:
    def test_has_name(self):
        provider = OllamaQwenProvider(model="qwen3.5:4b")
        assert provider.name == "ollama:qwen3.5:4b"

    def test_generate_raises_not_implemented(self):
        provider = OllamaQwenProvider(model="qwen3.5:4b")
        with pytest.raises(NotImplementedError):
            provider.generate_structured_ticket("test", "v1")

    def test_model_parameterization(self):
        p2b = OllamaQwenProvider(model="qwen3.5:2b")
        p9b = OllamaQwenProvider(model="qwen3.5:9b")
        assert p2b.name == "ollama:qwen3.5:2b"
        assert p9b.name == "ollama:qwen3.5:9b"


class TestCloudQwenProviderStub:
    def test_has_name(self):
        provider = CloudQwenProvider()
        assert provider.name == "cloud:qwen"

    def test_generate_raises_not_implemented(self):
        provider = CloudQwenProvider()
        with pytest.raises(NotImplementedError):
            provider.generate_structured_ticket("test", "v1")
