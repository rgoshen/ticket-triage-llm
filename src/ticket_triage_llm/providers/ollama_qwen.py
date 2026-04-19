import time

import ollama as ollama_client
from ollama import ResponseError

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
NUM_CTX = 16384


class OllamaQwenProvider:
    def __init__(self, model: str, base_url: str) -> None:
        self._model = model
        host = base_url.replace("/v1", "")
        self._client = ollama_client.Client(host=host)

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def generate_structured_ticket(
        self,
        ticket_body: str,
        prompt_version: str,
        ticket_subject: str = "",
    ) -> ModelResult:
        system_prompt, user_prompt = get_prompt(
            prompt_version, ticket_subject, ticket_body
        )

        start = time.perf_counter()
        try:
            response = self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "top_k": TOP_K,
                    "repeat_penalty": REPETITION_PENALTY,
                    "num_predict": MAX_TOKENS,
                    "num_ctx": NUM_CTX,
                },
                think=False,
            )
        except (ResponseError, ConnectionError) as exc:
            raise ProviderError(str(exc)) from exc
        elapsed_ms = (time.perf_counter() - start) * 1000

        raw_output = response.message.content or ""
        tokens_input = response.prompt_eval_count or 0
        tokens_output = response.eval_count or 0
        tokens_total = tokens_input + tokens_output

        return ModelResult(
            raw_output=raw_output,
            model=self._model,
            latency_ms=elapsed_ms,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            tokens_total=tokens_total,
            tokens_per_second=(
                (tokens_output / (elapsed_ms / 1000))
                if tokens_output and elapsed_ms > 0
                else None
            ),
        )
