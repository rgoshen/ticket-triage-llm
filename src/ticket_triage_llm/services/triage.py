"""Triage pipeline orchestration — Phase 2."""

import logging
import time
import uuid
from datetime import UTC, datetime

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import (
    TraceRecord,
    TriageFailure,
    TriageResult,
    TriageSuccess,
)
from ticket_triage_llm.services.guardrail import check_guardrail
from ticket_triage_llm.services.retry import validate_or_retry
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_triage(
    ticket_body: str,
    ticket_subject: str,
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
    guardrail_max_length: int = 10_000,
) -> tuple[TriageResult, TraceRecord]:
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    guardrail = check_guardrail(ticket_body, max_length=guardrail_max_length)

    if guardrail.decision == "block":
        result: TriageResult = TriageFailure(
            category="guardrail_blocked",
            detected_by="guardrail",
            message=f"Input blocked by guardrail rules: {guardrail.matched_rules}",
            retry_count=0,
        )
        trace = _build_and_save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail.decision,
            guardrail_matched_rules=guardrail.matched_rules,
            model_result=None,
            raw_output=None,
            result=result,
            retry_count=0,
        )
        return result, trace

    model_result: ModelResult | None = None
    try:
        model_result = provider.generate_structured_ticket(
            ticket_body, prompt_version, ticket_subject=ticket_subject
        )
    except ProviderError as exc:
        logger.warning("Provider error: %s", exc)
        result = TriageFailure(
            category="model_unreachable",
            detected_by="provider",
            message=str(exc),
            retry_count=0,
        )
        trace = _build_and_save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail.decision,
            guardrail_matched_rules=guardrail.matched_rules,
            model_result=None,
            raw_output=None,
            result=result,
            retry_count=0,
        )
        return result, trace

    retry = validate_or_retry(
        raw_output=model_result.raw_output,
        provider=provider,
        prompt_version=prompt_version,
        ticket_subject=ticket_subject,
        ticket_body=ticket_body,
    )

    validation_status = "valid"
    if retry.retry_count > 0 and isinstance(retry.result, TriageSuccess):
        validation_status = "valid_after_retry"
    elif isinstance(retry.result, TriageFailure):
        validation_status = "invalid"

    repair_mr = retry.repair_model_result
    if model_result and repair_mr:
        total_output = model_result.tokens_output + repair_mr.tokens_output
        total_ms = model_result.latency_ms + repair_mr.latency_ms
        combined_result = ModelResult(
            raw_output=repair_mr.raw_output,
            model=model_result.model,
            latency_ms=total_ms,
            tokens_input=model_result.tokens_input + repair_mr.tokens_input,
            tokens_output=total_output,
            tokens_total=model_result.tokens_total + repair_mr.tokens_total,
            tokens_per_second=(
                (total_output / (total_ms / 1000)) if total_ms > 0 else None
            ),
        )
    else:
        combined_result = model_result

    trace = _build_and_save_trace(
        trace_repo=trace_repo,
        request_id=request_id,
        start=start,
        provider=provider,
        prompt_version=prompt_version,
        ticket_body=ticket_body,
        guardrail_result=guardrail.decision,
        guardrail_matched_rules=guardrail.matched_rules,
        model_result=combined_result,
        raw_output=retry.final_raw_output,
        result=retry.result,
        retry_count=retry.retry_count,
        validation_status_override=validation_status,
    )
    return retry.result, trace


def _build_and_save_trace(
    *,
    trace_repo: TraceRepository,
    request_id: str,
    start: float,
    provider: LlmProvider,
    prompt_version: str,
    ticket_body: str,
    guardrail_result: str,
    guardrail_matched_rules: list[str],
    model_result: ModelResult | None,
    raw_output: str | None,
    result: TriageResult,
    retry_count: int,
    validation_status_override: str | None = None,
) -> TraceRecord:
    elapsed_ms = (time.perf_counter() - start) * 1000
    is_success = isinstance(result, TriageSuccess)

    triage_output_json = (
        result.output.model_dump_json(by_alias=True) if is_success else None
    )

    if validation_status_override:
        validation_status = validation_status_override
    else:
        validation_status = "valid" if is_success else "invalid"

    trace = TraceRecord(
        request_id=request_id,
        timestamp=datetime.now(UTC),
        model=model_result.model if model_result else "unknown",
        provider=provider.name,
        prompt_version=prompt_version,
        ticket_body=ticket_body,
        guardrail_result=guardrail_result,
        guardrail_matched_rules=guardrail_matched_rules,
        validation_status=validation_status,
        retry_count=retry_count,
        latency_ms=elapsed_ms,
        tokens_input=model_result.tokens_input if model_result else 0,
        tokens_output=model_result.tokens_output if model_result else 0,
        tokens_total=model_result.tokens_total if model_result else 0,
        tokens_per_second=model_result.tokens_per_second if model_result else None,
        status="success" if is_success else "failure",
        failure_category=(
            result.category if isinstance(result, TriageFailure) else None
        ),
        raw_model_output=raw_output,
        triage_output_json=triage_output_json,
    )
    trace_repo.save_trace(trace)
    return trace
