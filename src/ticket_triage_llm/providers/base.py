from typing import Protocol, runtime_checkable

from ticket_triage_llm.schemas.model_result import ModelResult


@runtime_checkable
class LlmProvider(Protocol):
    name: str

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult: ...
