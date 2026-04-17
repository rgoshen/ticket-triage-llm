"""Triage pipeline orchestration — Phase 1."""

import logging
import time
import uuid
from datetime import UTC, datetime

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.trace import (
    TraceRecord,
    TriageFailure,
    TriageResult,
    TriageSuccess,
)
from ticket_triage_llm.services.validation import parse_json, validate_schema
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_triage(
    ticket_body: str,
    ticket_subject: str,
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
) -> tuple[TriageResult, TraceRecord]:
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    # Phase 1: guardrail is a pass-through stub. Phase 2 adds real guardrail.
    guardrail_result = "pass"
    guardrail_matched_rules: list[str] = []

    model_result = None
    raw_output: str | None = None
    result: TriageResult

    try:
        model_result = provider.generate_structured_ticket(
            ticket_body, prompt_version, ticket_subject=ticket_subject
        )
        raw_output = model_result.raw_output
    except ProviderError as exc:
        logger.warning("Provider error: %s", exc)
        result = TriageFailure(
            category="model_unreachable",
            detected_by="provider",
            message=str(exc),
            retry_count=0,
        )
        trace = _save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail_result,
            guardrail_matched_rules=guardrail_matched_rules,
            model_result=model_result,
            raw_output=None,
            result=result,
        )
        return result, trace

    parsed = parse_json(raw_output)
    if parsed is None:
        result = TriageFailure(
            category="parse_failure",
            detected_by="parser",
            message="Failed to parse model output as JSON",
            raw_model_output=raw_output,
            retry_count=0,
        )
        trace = _save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail_result,
            guardrail_matched_rules=guardrail_matched_rules,
            model_result=model_result,
            raw_output=raw_output,
            result=result,
        )
        return result, trace

    triage_output = validate_schema(parsed)
    if triage_output is None:
        result = TriageFailure(
            category="schema_failure",
            detected_by="schema",
            message="Model output does not conform to TriageOutput schema",
            raw_model_output=raw_output,
            retry_count=0,
        )
        trace = _save_trace(
            trace_repo=trace_repo,
            request_id=request_id,
            start=start,
            provider=provider,
            prompt_version=prompt_version,
            ticket_body=ticket_body,
            guardrail_result=guardrail_result,
            guardrail_matched_rules=guardrail_matched_rules,
            model_result=model_result,
            raw_output=raw_output,
            result=result,
        )
        return result, trace

    result = TriageSuccess(
        output=triage_output,
        retry_count=0,
    )

    trace = _save_trace(
        trace_repo=trace_repo,
        request_id=request_id,
        start=start,
        provider=provider,
        prompt_version=prompt_version,
        ticket_body=ticket_body,
        guardrail_result=guardrail_result,
        guardrail_matched_rules=guardrail_matched_rules,
        model_result=model_result,
        raw_output=raw_output,
        result=result,
    )
    return result, trace


def _save_trace(
    *,
    trace_repo: TraceRepository,
    request_id: str,
    start: float,
    provider: LlmProvider,
    prompt_version: str,
    ticket_body: str,
    guardrail_result: str,
    guardrail_matched_rules: list[str],
    model_result: object | None,
    raw_output: str | None,
    result: TriageResult,
) -> TraceRecord:
    elapsed_ms = (time.perf_counter() - start) * 1000

    is_success = isinstance(result, TriageSuccess)
    triage_output_json = (
        result.output.model_dump_json(by_alias=True) if is_success else None
    )

    mr = model_result
    trace = TraceRecord(
        request_id=request_id,
        timestamp=datetime.now(UTC),
        model=mr.model if mr else "unknown",
        provider=provider.name,
        prompt_version=prompt_version,
        ticket_body=ticket_body,
        guardrail_result=guardrail_result,
        guardrail_matched_rules=guardrail_matched_rules,
        validation_status="valid" if is_success else "invalid",
        retry_count=0,
        latency_ms=elapsed_ms,
        tokens_input=mr.tokens_input if mr else 0,
        tokens_output=mr.tokens_output if mr else 0,
        tokens_total=mr.tokens_total if mr else 0,
        tokens_per_second=mr.tokens_per_second if mr else None,
        status="success" if is_success else "failure",
        failure_category=(
            result.category if isinstance(result, TriageFailure) else None
        ),
        raw_model_output=raw_output,
        triage_output_json=triage_output_json,
    )
    trace_repo.save_trace(trace)
    return trace
