"""Adversarial assessment runner — Phase 4."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from ticket_triage_llm.eval.compliance import (
    ComplianceCheck,
    check_compliance,
)
from ticket_triage_llm.eval.datasets import (
    AdversarialTicketRecord,
    TicketRecord,
    adversarial_to_ticket_record,
    load_adversarial_dataset,
    load_dataset,
)
from ticket_triage_llm.eval.results import (
    AdversarialSummary,
    LayerAccounting,
    compute_layer_accounting,
)
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.trace import TraceRecord, TriageFailure, TriageSuccess
from ticket_triage_llm.schemas.triage_output import TriageOutput
from ticket_triage_llm.services.guardrail import check_guardrail
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def compute_false_positive_baseline(
    normal_tickets: list[TicketRecord],
    guardrail_max_length: int = 10_000,
) -> tuple[float, list[dict]]:
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


def _compute_per_rule_stats(
    traces: list[TraceRecord],
    ticket_categories: dict[str, str],
) -> tuple[dict[str, int], dict[str, list[str]]]:
    hits: dict[str, int] = {}
    rule_cats: dict[str, set[str]] = {}
    unknown_ids: set[str] = set()

    for trace in traces:
        tid = trace.ticket_id or ""
        cat = ticket_categories.get(tid)
        if cat is None:
            cat = "unknown"
            if tid and tid not in unknown_ids:
                unknown_ids.add(tid)
                logger.warning(
                    "Per-rule stats: trace ticket_id=%r not in "
                    "ticket_categories — bucketing as 'unknown'. "
                    "Expected ids: %s",
                    tid,
                    sorted(ticket_categories.keys())[:10],
                )
        for rule in trace.guardrail_matched_rules:
            hits[rule] = hits.get(rule, 0) + 1
            if rule not in rule_cats:
                rule_cats[rule] = set()
            rule_cats[rule].add(cat)

    return hits, {k: sorted(v) for k, v in rule_cats.items()}


def run_adversarial_eval(
    providers: list[LlmProvider],
    adv_tickets: list[AdversarialTicketRecord],
    normal_tickets: list[TicketRecord],
    trace_repo: TraceRepository,
    run_suffix: str = "",
) -> list[AdversarialSummary]:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M")
    suffix = f"-{run_suffix}" if run_suffix else ""

    logger.info(
        "Computing false-positive baseline on %d normal tickets...",
        len(normal_tickets),
    )
    fp_rate, fp_details = compute_false_positive_baseline(normal_tickets)
    logger.info(
        "False-positive rate: %.1f%% (%d/%d)",
        fp_rate * 100,
        len(fp_details),
        len(normal_tickets),
    )

    adapted = [adversarial_to_ticket_record(t) for t in adv_tickets]
    ticket_categories = {t.id: t.attack_category for t in adv_tickets}
    adv_by_id = {t.id: t for t in adv_tickets}

    summaries: list[AdversarialSummary] = []

    for provider in providers:
        tag = provider.name.split(":")[-1] if ":" in provider.name else provider.name
        run_id = f"adv-{tag}-{timestamp}{suffix}"
        logger.info("Adversarial: %s — run_id=%s", provider.name, run_id)

        traces = run_experiment_pass(
            tickets=adapted,
            provider=provider,
            prompt_version="v1",
            trace_repo=trace_repo,
            run_id=run_id,
        )

        compliance_checks: list[ComplianceCheck] = []
        for trace in traces:
            tid = trace.ticket_id or ""
            adv_ticket = adv_by_id.get(tid)
            if adv_ticket is None:
                continue

            if trace.status == "success" and trace.triage_output_json:
                try:
                    output = TriageOutput.model_validate_json(trace.triage_output_json)
                    triage_result = TriageSuccess(
                        output=output, retry_count=trace.retry_count
                    )
                except Exception as exc:
                    logger.warning(
                        "Corrupt trace for ticket_id=%s in run_id=%s — "
                        "reconstructing as schema_failure for compliance "
                        "analysis (%s)",
                        tid,
                        run_id,
                        type(exc).__name__,
                    )
                    triage_result = TriageFailure(
                        category="schema_failure",
                        detected_by="parser",
                        message=(
                            f"Reconstructed from corrupt trace ({type(exc).__name__})"
                        ),
                        retry_count=trace.retry_count,
                    )
            else:
                triage_result = TriageFailure(
                    category=trace.failure_category or "parse_failure",
                    detected_by="parser",
                    message="Reconstructed from trace",
                    retry_count=trace.retry_count,
                )

            check = check_compliance(adv_ticket, triage_result, trace)
            compliance_checks.append(check)

        per_category = compute_layer_accounting(
            traces, compliance_checks, ticket_categories
        )

        totals = LayerAccounting(
            attack_category="ALL",
            ticket_count=sum(c.ticket_count for c in per_category),
            guardrail_blocked=sum(c.guardrail_blocked for c in per_category),
            guardrail_warned=sum(c.guardrail_warned for c in per_category),
            reached_model=sum(c.reached_model for c in per_category),
            model_complied=sum(c.model_complied for c in per_category),
            validation_caught=sum(c.validation_caught for c in per_category),
            residual_risk=sum(c.residual_risk for c in per_category),
        )

        per_rule_hits, per_rule_categories = _compute_per_rule_stats(
            traces, ticket_categories
        )

        needs_review = [c.ticket_id for c in compliance_checks if c.complied is None]

        failed = [
            t.ticket_id or "unknown"
            for t in traces
            if t.failure_category == "model_unreachable"
        ]
        unreachable_rate = len(failed) / len(traces) if traces else 0.0
        run_status = "degraded" if unreachable_rate > 0.25 else "complete"
        if unreachable_rate > 0.25:
            logger.error(
                "%s: run degraded — %d/%d tickets unreachable (%.0f%%)",
                provider.name,
                len(failed),
                len(traces),
                unreachable_rate * 100,
            )

        summary = AdversarialSummary(
            model=provider.name,
            run_id=run_id,
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            per_category=per_category,
            totals=totals,
            per_rule_hits=per_rule_hits,
            per_rule_categories=per_rule_categories,
            false_positive_rate=fp_rate,
            false_positive_details=fp_details,
            compliance_checks=[
                {
                    "ticket_id": c.ticket_id,
                    "attack_category": c.attack_category,
                    "complied": c.complied,
                    "evidence": c.evidence,
                }
                for c in compliance_checks
            ],
            needs_manual_review=needs_review,
            run_status=run_status,
            failed_tickets=failed if failed else None,
        )
        summaries.append(summary)

        logger.info(
            "%s: blocked=%d reached=%d complied=%d caught=%d residual=%d review=%d",
            provider.name,
            totals.guardrail_blocked,
            totals.reached_model,
            totals.model_complied,
            totals.validation_caught,
            totals.residual_risk,
            len(needs_review),
        )

    return summaries


if __name__ == "__main__":
    import argparse

    from ticket_triage_llm.config import Settings
    from ticket_triage_llm.providers.ollama_qwen import OllamaQwenProvider
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="Phase 4: adversarial assessment")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--adversarial-path", default="data/adversarial_set.jsonl")
    parser.add_argument("--normal-path", default="data/normal_set.jsonl")
    parser.add_argument("--output-dir", default="data/phase4")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    settings = Settings()
    models = [m.strip() for m in settings.ollama_models.split(",") if m.strip()]
    if not models:
        models = [settings.ollama_model]

    providers = [
        OllamaQwenProvider(model=m, base_url=settings.ollama_base_url) for m in models
    ]

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)

    adv_tickets = load_adversarial_dataset(Path(args.adversarial_path))
    normal_tickets = load_dataset(Path(args.normal_path))

    summaries = run_adversarial_eval(providers, adv_tickets, normal_tickets, repo)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in summaries:
        tag = s.model.split(":")[-1] if ":" in s.model else s.model
        out_path = out_dir / f"adversarial-{tag}.json"
        out_path.write_text(json.dumps(s.to_dict(), indent=2))
        logger.info("Results written to %s", out_path)
