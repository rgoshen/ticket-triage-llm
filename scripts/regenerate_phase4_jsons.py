"""Regenerate Phase 4 adversarial JSONs from existing SQLite traces.

Reads the three completed adversarial runs from data/traces.db and
recomputes compliance + layer accounting using the current (fixed) code.
No Ollama / GPU required — this is pure reinterpretation of existing data.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from ticket_triage_llm.eval.compliance import check_compliance
from ticket_triage_llm.eval.datasets import (
    load_adversarial_dataset,
    load_dataset,
)
from ticket_triage_llm.eval.results import (
    AdversarialSummary,
    LayerAccounting,
    compute_layer_accounting,
)
from ticket_triage_llm.eval.runners.run_adversarial_eval import (
    _compute_per_rule_stats,
    compute_false_positive_baseline,
)
from ticket_triage_llm.schemas.trace import TriageFailure, TriageSuccess
from ticket_triage_llm.schemas.triage_output import TriageOutput
from ticket_triage_llm.storage.db import get_connection

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

RUN_IDS = {
    "2b": "adv-2b-20260418T1838",
    "4b": "adv-4b-20260418T1838",
    "9b": "adv-9b-20260418T1838",
}

DB_PATH = "data/traces.db"
ADV_PATH = "data/adversarial_set.jsonl"
NORMAL_PATH = "data/normal_set.jsonl"
OUT_DIR = Path("data/phase4")


def _load_traces(conn, run_id: str) -> list:
    from ticket_triage_llm.schemas.trace import TraceRecord

    cur = conn.cursor()
    cur.execute(
        """SELECT request_id, run_id, ticket_id, timestamp, model, provider,
                  prompt_version, ticket_body, guardrail_result,
                  guardrail_matched_rules, validation_status, retry_count,
                  latency_ms, status, failure_category, triage_output_json,
                  tokens_input, tokens_output, tokens_per_second
           FROM traces WHERE run_id = ? ORDER BY ticket_id""",
        (run_id,),
    )
    rows = cur.fetchall()
    traces = []
    for r in rows:
        matched_rules = json.loads(r[9]) if r[9] else []
        traces.append(
            TraceRecord(
                request_id=r[0],
                run_id=r[1],
                ticket_id=r[2],
                timestamp=r[3],
                model=r[4],
                provider=r[5],
                prompt_version=r[6],
                ticket_body=r[7],
                guardrail_result=r[8],
                guardrail_matched_rules=matched_rules,
                validation_status=r[10],
                retry_count=r[11] or 0,
                latency_ms=r[12],
                status=r[13],
                failure_category=r[14],
                triage_output_json=r[15],
                input_tokens=r[16],
                output_tokens=r[17],
                tokens_per_second=r[18],
            )
        )
    return traces


def main():
    conn = get_connection(DB_PATH)
    adv_tickets = load_adversarial_dataset(Path(ADV_PATH))
    normal_tickets = load_dataset(Path(NORMAL_PATH))

    fp_rate, fp_details = compute_false_positive_baseline(normal_tickets)
    logger.info(
        "False-positive rate: %.1f%% (%d/%d)",
        fp_rate * 100,
        len(fp_details),
        len(normal_tickets),
    )

    adv_by_id = {t.id: t for t in adv_tickets}
    ticket_categories = {t.id: t.attack_category for t in adv_tickets}

    for tag, run_id in RUN_IDS.items():
        logger.info("\n=== Regenerating %s (run_id=%s) ===", tag, run_id)
        traces = _load_traces(conn, run_id)
        logger.info("Loaded %d traces", len(traces))

        compliance_checks = []
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
                        "Corrupt trace for ticket_id=%s — reconstructing "
                        "as schema_failure for compliance analysis (%s)",
                        tid,
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
            logger.info(
                "  %s: complied=%s — %s",
                tid,
                check.complied,
                check.evidence,
            )

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

        summary = AdversarialSummary(
            model=traces[0].provider if traces else f"ollama:qwen3.5:{tag}",
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
            run_status="degraded" if unreachable_rate > 0.25 else "complete",
            failed_tickets=failed if failed else None,
        )

        out_path = OUT_DIR / f"adversarial-{tag}.json"
        out_path.write_text(json.dumps(summary.to_dict(), indent=2))
        logger.info("Written to %s", out_path)
        logger.info(
            "Totals: blocked=%d reached=%d complied=%d caught=%d residual=%d review=%d",
            totals.guardrail_blocked,
            totals.reached_model,
            totals.model_complied,
            totals.validation_caught,
            totals.residual_risk,
            len(needs_review),
        )

    conn.close()


if __name__ == "__main__":
    main()
