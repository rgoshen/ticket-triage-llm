from ticket_triage_llm.schemas.model_result import ModelResult


class OllamaQwenProvider:
    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        raise NotImplementedError(
            f"OllamaQwenProvider({self._model}) is a stub — "
            "concrete implementation belongs to Phase 1."
        )
