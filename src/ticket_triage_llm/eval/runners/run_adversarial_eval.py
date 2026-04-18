"""Adversarial assessment runner — Phase 4."""

from ticket_triage_llm.eval.datasets import TicketRecord
from ticket_triage_llm.services.guardrail import check_guardrail


def compute_false_positive_baseline(
    normal_tickets: list[TicketRecord],
    guardrail_max_length: int = 10_000,
) -> tuple[float, list[dict]]:
    """Compute false positive rate of guardrail on normal tickets.

    Args:
        normal_tickets: List of normal (non-adversarial) tickets
        guardrail_max_length: Maximum length for guardrail check

    Returns:
        Tuple of (false_positive_rate, false_positive_details)
        where details contains list of dicts with ticket_id, decision, matched_rules
    """
    if not normal_tickets:
        return 0.0, []

    details: list[dict] = []
    for ticket in normal_tickets:
        result = check_guardrail(ticket.body, max_length=guardrail_max_length)
        if result.decision != "pass":
            details.append(
                {
                    "ticket_id": ticket.id,
                    "decision": result.decision,
                    "matched_rules": result.matched_rules,
                }
            )

    rate = len(details) / len(normal_tickets)
    return rate, details
