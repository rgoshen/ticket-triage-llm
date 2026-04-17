import pytest

from ticket_triage_llm.services.provider_router import ProviderRegistry


class FakeProvider:
    def __init__(self, name: str = "fake:model"):
        self.name = name

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ):
        raise NotImplementedError


class TestProviderRegistryRegisterAndGet:
    def test_register_and_get_by_name(self):
        registry = ProviderRegistry()
        provider = FakeProvider("ollama:qwen3.5:4b")
        registry.register(provider)
        assert registry.get("ollama:qwen3.5:4b") is provider

    def test_get_unknown_raises_key_error(self):
        registry = ProviderRegistry()
        with pytest.raises(KeyError, match="no-such-provider"):
            registry.get("no-such-provider")

    def test_duplicate_registration_overwrites(self):
        registry = ProviderRegistry()
        first = FakeProvider("ollama:qwen3.5:4b")
        second = FakeProvider("ollama:qwen3.5:4b")
        registry.register(first)
        registry.register(second)
        assert registry.get("ollama:qwen3.5:4b") is second


class TestProviderRegistryListNames:
    def test_list_names_returns_registered_names(self):
        registry = ProviderRegistry()
        registry.register(FakeProvider("ollama:qwen3.5:2b"))
        registry.register(FakeProvider("ollama:qwen3.5:4b"))
        names = registry.list_names()
        assert "ollama:qwen3.5:2b" in names
        assert "ollama:qwen3.5:4b" in names

    def test_list_names_empty_registry(self):
        registry = ProviderRegistry()
        assert registry.list_names() == []


class TestProviderRegistryDefault:
    def test_default_returns_first_registered(self):
        registry = ProviderRegistry()
        first = FakeProvider("ollama:qwen3.5:2b")
        registry.register(first)
        registry.register(FakeProvider("ollama:qwen3.5:4b"))
        assert registry.default() is first

    def test_default_empty_raises_runtime_error(self):
        registry = ProviderRegistry()
        with pytest.raises(RuntimeError, match="empty"):
            registry.default()
