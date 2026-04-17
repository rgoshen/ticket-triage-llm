"""Provider registry and selection — Phase 2."""

from ticket_triage_llm.providers.base import LlmProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, LlmProvider] = {}

    def register(self, provider: LlmProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> LlmProvider:
        try:
            return self._providers[name]
        except KeyError:
            raise KeyError(f"No provider registered with name {name!r}") from None

    def list_names(self) -> list[str]:
        return list(self._providers.keys())

    def default(self) -> LlmProvider:
        if not self._providers:
            raise RuntimeError("Provider registry is empty")
        return next(iter(self._providers.values()))
