import pytest

from ticket_triage_llm.providers.base import LlmProvider
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
