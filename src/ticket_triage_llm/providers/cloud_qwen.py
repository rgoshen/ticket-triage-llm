from ticket_triage_llm.schemas.model_result import ModelResult


class CloudQwenProvider:
    name: str = "cloud:qwen"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        raise NotImplementedError(
            "CloudQwenProvider is a placeholder — "
            "cloud integration is deferred to future work (OD-2)."
        )
