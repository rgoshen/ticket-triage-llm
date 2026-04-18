"""Aggregate and summarize experiment results — Phase 3."""

import json
import logging
import re
import statistics
from datetime import UTC, datetime

from ticket_triage_llm.eval.datasets import TicketRecord
from ticket_triage_llm.eval.results import ExperimentSummary, ModelMetrics
from ticket_triage_llm.services.validation import parse_json
from ticket_triage_llm.storage.trace_repo import TraceRepository

logger = logging.getLogger(__name__)


def _percentile(values: list[float], pct: float) -> float:
    """Compute the given percentile from a sorted list using linear interpolation."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[f]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def summarize_run(
    run_id: str,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ModelMetrics:
    """Aggregate traces for a single run into metrics.

    Fetches all traces tagged with *run_id*, joins each to its ground
    truth via ticket_id, and computes the full ModelMetrics covering
    accuracy, reliability, and latency.

    Rules:
    - Only traces with status="success" AND a valid
      triage_output_json contribute to accuracy numerators.
    - Failed traces count as incorrect for ALL accuracy fields
      (they are in the denominator but never in the numerator).
    - json_valid_rate = parse_json(raw_model_output) != None / total
    - schema_pass_rate = validation_status in
      ("valid", "valid_after_retry") / total
    - retry_rate = traces where retry_count > 0 / total
    - retry_success_rate = retried AND success / retried
    """
    traces = trace_repo.get_traces_by_run(run_id)
    if not traces:
        raise ValueError(f"No traces found for run_id={run_id!r}")

    gt_by_id = {t.id: t.ground_truth for t in tickets}
    total = len(traces)

    category_correct = 0
    severity_correct = 0
    routing_correct = 0
    escalation_correct = 0
    successful = 0
    json_valid = 0
    schema_pass = 0
    retried = 0
    retry_succeeded = 0
    latencies: list[float] = []
    tps_values: list[float] = []
    tokens_in: list[int] = []
    tokens_out: list[int] = []
    tokens_tot: list[int] = []

    for trace in traces:
        latencies.append(trace.latency_ms)
        tokens_in.append(trace.tokens_input)
        tokens_out.append(trace.tokens_output)
        tokens_tot.append(trace.tokens_total)
        if trace.tokens_per_second is not None:
            tps_values.append(trace.tokens_per_second)

        if trace.raw_model_output and parse_json(trace.raw_model_output) is not None:
            json_valid += 1

        if trace.validation_status in ("valid", "valid_after_retry"):
            schema_pass += 1

        if trace.retry_count > 0:
            retried += 1
            if trace.status == "success":
                retry_succeeded += 1

        if trace.status != "success" or not trace.triage_output_json:
            continue

        successful += 1
        gt = gt_by_id.get(trace.ticket_id) if trace.ticket_id else None
        if gt is None:
            logger.warning(
                "Trace %s has ticket_id=%r with no matching ground truth",
                trace.request_id,
                trace.ticket_id,
            )
            continue

        output = json.loads(trace.triage_output_json)
        if output.get("category") == gt.category:
            category_correct += 1
        if output.get("severity") == gt.severity:
            severity_correct += 1
        routing = output.get("routingTeam") or output.get("routing_team")
        if routing == gt.routing_team:
            routing_correct += 1
        if output.get("escalation") == gt.escalation:
            escalation_correct += 1

    return ModelMetrics(
        model=traces[0].model,
        run_id=run_id,
        category_accuracy=category_correct / total if total else 0.0,
        severity_accuracy=severity_correct / total if total else 0.0,
        routing_accuracy=routing_correct / total if total else 0.0,
        escalation_accuracy=escalation_correct / total if total else 0.0,
        json_valid_rate=json_valid / total if total else 0.0,
        schema_pass_rate=schema_pass / total if total else 0.0,
        retry_rate=retried / total if total else 0.0,
        retry_success_rate=retry_succeeded / retried if retried else 0.0,
        avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        avg_tokens_per_second=(statistics.mean(tps_values) if tps_values else None),
        avg_tokens_input=statistics.mean(tokens_in) if tokens_in else 0.0,
        avg_tokens_output=statistics.mean(tokens_out) if tokens_out else 0.0,
        avg_tokens_total=statistics.mean(tokens_tot) if tokens_tot else 0.0,
        total_tickets=total,
        successful_tickets=successful,
    )


def compose_e2(
    e1_summary: ExperimentSummary,
    e2_9b_noval_run_id: str,
    tickets: list[TicketRecord],
    trace_repo: TraceRepository,
) -> ExperimentSummary:
    """Build Experiment 2 summary from E1's smallest model + a 9B-no-validation run.

    Experiment 2 ("Model size vs engineering controls") compares the smallest
    model *with* full validation against the largest model *without* validation,
    answering whether engineering controls compensate for model size.
    """

    def _extract_size(model_name: str) -> float:
        match = re.search(r"(\d+(?:\.\d+)?)b", model_name.lower())
        if not match:
            raise ValueError(
                f"Cannot parse model size from {model_name!r}"
                " — expected a name containing a size like '2b' or '9b'"
            )
        return float(match.group(1))

    smallest_metrics = min(
        e1_summary.model_metrics, key=lambda m: _extract_size(m.model)
    )

    largest_noval_metrics = summarize_run(e2_9b_noval_run_id, tickets, trace_repo)

    return ExperimentSummary(
        experiment_id="E2",
        experiment_name="Model size vs engineering controls",
        date=datetime.now(UTC).strftime("%Y-%m-%d"),
        dataset_size=len(tickets),
        prompt_version="v1",
        model_metrics=[smallest_metrics, largest_noval_metrics],
    )


def _print_metrics(m: ModelMetrics) -> None:
    print(f"  Model:              {m.model}")
    print(f"  Run ID:             {m.run_id}")
    print(f"  Category accuracy:  {m.category_accuracy:.1%}")
    print(f"  Severity accuracy:  {m.severity_accuracy:.1%}")
    print(f"  Routing accuracy:   {m.routing_accuracy:.1%}")
    print(f"  Escalation acc:     {m.escalation_accuracy:.1%}")
    print(f"  JSON valid rate:    {m.json_valid_rate:.1%}")
    print(f"  Schema pass rate:   {m.schema_pass_rate:.1%}")
    print(f"  Retry rate:         {m.retry_rate:.1%}")
    print(f"  Retry success rate: {m.retry_success_rate:.1%}")
    print(f"  Avg latency:        {m.avg_latency_ms:.0f}ms")
    print(f"  p50 latency:        {m.p50_latency_ms:.0f}ms")
    print(f"  p95 latency:        {m.p95_latency_ms:.0f}ms")
    tps = f"{m.avg_tokens_per_second:.1f}" if m.avg_tokens_per_second else "N/A"
    print(f"  Avg tokens/sec:     {tps}")
    print(f"  Avg tokens in:      {m.avg_tokens_input:.0f}")
    print(f"  Avg tokens out:     {m.avg_tokens_output:.0f}")
    print(f"  Tickets:            {m.successful_tickets}/{m.total_tickets}")
    print()


if __name__ == "__main__":
    import argparse
    import logging
    from pathlib import Path

    from ticket_triage_llm.eval.datasets import load_dataset
    from ticket_triage_llm.services.trace import SqliteTraceRepository
    from ticket_triage_llm.storage.db import get_connection, init_schema

    parser = argparse.ArgumentParser(description="Summarize experiment results")
    parser.add_argument("--db-path", default="data/traces.db")
    parser.add_argument("--dataset-path", default="data/normal_set.jsonl")
    parser.add_argument("--run-id", required=True, help="Run ID to summarize")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    conn = get_connection(args.db_path)
    init_schema(conn)
    repo = SqliteTraceRepository(conn)
    tickets = load_dataset(Path(args.dataset_path))

    metrics = summarize_run(args.run_id, tickets, repo)
    _print_metrics(metrics)
