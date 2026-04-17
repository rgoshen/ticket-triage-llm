"""Bounded retry policy — Phase 2.

Exactly one retry on validation failure using a repair prompt (ADR 0002).
The repair prompt includes the failed output and specific error message.
"""

import logging
from dataclasses import dataclass

from ticket_triage_llm.prompts.repair_json_v1 import (
    REPAIR_SYSTEM_PROMPT,
    build_repair_user_prompt,
)
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.trace import TriageFailure, TriageResult, TriageSuccess
from ticket_triage_llm.services.validation import (
    parse_json,
    validate_schema_with_error,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryResult:
    result: TriageResult
    retry_count: int
    final_raw_output: str | None


def _attempt_repair(
    provider: LlmProvider,
    raw_output: str,
    error_message: str,
) -> str | None:
    try:
        repair_result = provider.generate_structured_ticket(
            ticket_body=build_repair_user_prompt(raw_output, error_message),
            prompt_version="__repair__",
            ticket_subject=REPAIR_SYSTEM_PROMPT,
        )
        return repair_result.raw_output
    except ProviderError as exc:
        logger.warning("Provider error during retry: %s", exc)
        return None


def validate_or_retry(
    raw_output: str,
    provider: LlmProvider,
    prompt_version: str,
    ticket_subject: str,
    ticket_body: str,
) -> RetryResult:
    parsed = parse_json(raw_output)

    if parsed is None:
        repair_raw = _attempt_repair(
            provider, raw_output, "Failed to parse output as JSON"
        )
        if repair_raw is None:
            return RetryResult(
                result=TriageFailure(
                    category="model_unreachable",
                    detected_by="provider",
                    message="Provider error during repair attempt",
                    raw_model_output=raw_output,
                    retry_count=1,
                ),
                retry_count=1,
                final_raw_output=raw_output,
            )

        parsed = parse_json(repair_raw)
        if parsed is None:
            return RetryResult(
                result=TriageFailure(
                    category="parse_failure",
                    detected_by="parser",
                    message="Failed to parse repaired output as JSON",
                    raw_model_output=repair_raw,
                    retry_count=1,
                ),
                retry_count=1,
                final_raw_output=repair_raw,
            )

        output, schema_error = validate_schema_with_error(parsed)
        if output is None:
            return RetryResult(
                result=TriageFailure(
                    category="schema_failure",
                    detected_by="schema",
                    message=f"Repaired output failed schema validation: {schema_error}",
                    raw_model_output=repair_raw,
                    retry_count=1,
                ),
                retry_count=1,
                final_raw_output=repair_raw,
            )

        return RetryResult(
            result=TriageSuccess(output=output, retry_count=1),
            retry_count=1,
            final_raw_output=repair_raw,
        )

    output, schema_error = validate_schema_with_error(parsed)
    if output is not None:
        return RetryResult(
            result=TriageSuccess(output=output, retry_count=0),
            retry_count=0,
            final_raw_output=raw_output,
        )

    repair_raw = _attempt_repair(
        provider, raw_output, f"Schema validation failed: {schema_error}"
    )
    if repair_raw is None:
        return RetryResult(
            result=TriageFailure(
                category="model_unreachable",
                detected_by="provider",
                message="Provider error during repair attempt",
                raw_model_output=raw_output,
                retry_count=1,
            ),
            retry_count=1,
            final_raw_output=raw_output,
        )

    repair_parsed = parse_json(repair_raw)
    if repair_parsed is None:
        return RetryResult(
            result=TriageFailure(
                category="schema_failure",
                detected_by="schema",
                message=(
                    f"Original schema error: {schema_error}; "
                    "repair produced unparseable output"
                ),
                raw_model_output=repair_raw,
                retry_count=1,
            ),
            retry_count=1,
            final_raw_output=repair_raw,
        )

    repair_output, repair_schema_error = validate_schema_with_error(repair_parsed)
    if repair_output is None:
        return RetryResult(
            result=TriageFailure(
                category="schema_failure",
                detected_by="schema",
                message=f"Repair also failed schema validation: {repair_schema_error}",
                raw_model_output=repair_raw,
                retry_count=1,
            ),
            retry_count=1,
            final_raw_output=repair_raw,
        )

    return RetryResult(
        result=TriageSuccess(output=repair_output, retry_count=1),
        retry_count=1,
        final_raw_output=repair_raw,
    )
