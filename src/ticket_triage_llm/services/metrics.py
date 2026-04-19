"""Metrics aggregation from traces — Phase 5."""

import statistics
from datetime import UTC, datetime, timedelta

from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.storage.trace_repo import TraceRepository

EXPERIMENT_PREFIXES = {
    "e1-": "E1: Model Size Comparison",
    "e2-": "E2: Model Size vs Engineering Controls",
    "e3-": "E3: Validation Impact",
    "e4-": "E4: Prompt Comparison",
    "adv-": "Adversarial: Injection Defense",
}


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (pct / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[f]
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def list_run_ids(trace_repo: TraceRepository) -> list[dict]:
    return trace_repo.get_distinct_run_ids()


def _get_live_traces(
    trace_repo: TraceRepository, window_hours: int | None
) -> list[TraceRecord]:
    if window_hours is not None:
        since = datetime.now(UTC) - timedelta(hours=window_hours)
        all_traces = trace_repo.get_traces_since(since)
    else:
        all_traces = trace_repo.get_all_traces()
    return [t for t in all_traces if t.run_id is None]


def get_live_summary(trace_repo: TraceRepository, window_hours: int | None) -> dict:
    traces = _get_live_traces(trace_repo, window_hours)
    total = len(traces)
    if total == 0:
        return {
            "total_requests": 0,
            "success_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p50_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "retry_rate": 0.0,
            "error_rate": 0.0,
        }

    successes = sum(1 for t in traces if t.status == "success")
    retried = sum(1 for t in traces if t.retry_count > 0)
    latencies = [t.latency_ms for t in traces]

    return {
        "total_requests": total,
        "success_rate": successes / total,
        "avg_latency_ms": statistics.mean(latencies),
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "retry_rate": retried / total,
        "error_rate": (total - successes) / total,
    }


def group_runs_by_experiment(run_ids: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for run in run_ids:
        rid = run["run_id"]
        matched = False
        for prefix, name in EXPERIMENT_PREFIXES.items():
            if rid.startswith(prefix):
                groups.setdefault(name, []).append(run)
                matched = True
                break
        if not matched:
            groups.setdefault("Other", []).append(run)
    return groups
