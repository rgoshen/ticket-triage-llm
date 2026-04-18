"""Shared eval runner infrastructure — Phase 3."""

import logging

from ticket_triage_llm.eval.datasets import TicketRecord
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def run_experiment_pass(
    tickets: list[TicketRecord],
    provider: LlmProvider,
    prompt_version: str,
    trace_repo: TraceRepository,
    run_id: str,
    skip_validation: bool = False,
    guardrail_max_length: int = 10_000,
) -> list[TraceRecord]:
    """Execute one experiment pass over a list of tickets.

    Args:
        tickets: List of tickets with ground truth
        provider: LLM provider instance
        prompt_version: Prompt version string
        trace_repo: Trace repository for persistence
        run_id: Experiment run identifier
        skip_validation: If True, skip validation and set status to 'skipped'
        guardrail_max_length: Max allowed ticket body length

    Returns:
        List of trace records (one per ticket)
    """
    traces: list[TraceRecord] = []
    total = len(tickets)
    for i, ticket in enumerate(tickets, 1):
        result, trace = run_triage(
            ticket_body=ticket.body,
            ticket_subject=ticket.subject,
            provider=provider,
            prompt_version=prompt_version,
            trace_repo=trace_repo,
            guardrail_max_length=guardrail_max_length,
            skip_validation=skip_validation,
            run_id=run_id,
            ticket_id=ticket.id,
        )
        traces.append(trace)
        logger.info(
            "[%d/%d] ticket %s — %s — %.0fms",
            i,
            total,
            ticket.id,
            trace.status,
            trace.latency_ms,
        )
    return traces
