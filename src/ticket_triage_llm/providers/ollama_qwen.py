import time

from openai import APIConnectionError, APITimeoutError, OpenAI

from ticket_triage_llm.config import (
    REPETITION_PENALTY,
    TEMPERATURE,
    TOP_K,
    TOP_P,
)
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.services.prompt import get_prompt

MAX_TOKENS = 2048


class OllamaQwenProvider:
    def __init__(self, model: str, base_url: str) -> None:
        self._model = model
        self._client = OpenAI(base_url=base_url, api_key="ollama")

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str
    ) -> ModelResult:
        system_prompt, user_prompt = get_prompt(prompt_version, "", ticket_body)

        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                extra_body={
                    "top_p": TOP_P,
                    "top_k": TOP_K,
                    "repetition_penalty": REPETITION_PENALTY,
                },
            )
        except (APIConnectionError, APITimeoutError) as exc:
            raise ProviderError(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        raw_output = response.choices[0].message.content or ""
        usage = response.usage

        return ModelResult(
            raw_output=raw_output,
            model=self._model,
            latency_ms=elapsed_ms,
            tokens_input=usage.prompt_tokens if usage else 0,
            tokens_output=usage.completion_tokens if usage else 0,
            tokens_total=usage.total_tokens if usage else 0,
            tokens_per_second=(
                (usage.completion_tokens / (elapsed_ms / 1000))
                if usage and elapsed_ms > 0
                else None
            ),
        )
