import json
from datetime import UTC, datetime

import pytest

from ticket_triage_llm.eval.datasets import GroundTruth, TicketRecord
from ticket_triage_llm.eval.runners.summarize_results import summarize_run
from ticket_triage_llm.schemas.trace import TraceRecord

VALID_OUTPUT = {
    "category": "billing",
    "severity": "medium",
    "routingTeam": "billing",
    "summary": "Billing issue",
    "businessImpact": "Cannot process payments",
    "draftReply": "We are looking into it.",
    "confidence": 0.85,
    "escalation": False,
}

TICKETS = [
    TicketRecord(
        id="n-001",
        subject="Billing issue",
        body="I have a billing question",
        ground_truth=GroundTruth(
            category="billing",
            severity="medium",
            routing_team="billing",
            escalation=False,
        ),
    ),
    TicketRecord(
        id="n-002",
        subject="Account access",
        body="Cannot log in",
        ground_truth=GroundTruth(
            category="account_access",
            severity="high",
            routing_team="support",
            escalation=False,
        ),
    ),
]


def _make_trace(
    request_id: str,
    run_id: str,
    ticket_id: str,
    triage_output: dict | None = None,
    status: str = "success",
    failure_category: str | None = None,
    validation_status: str = "valid",
    retry_count: int = 0,
    latency_ms: float = 1500.0,
    tokens_input: int = 100,
    tokens_output: int = 50,
    tokens_total: int = 150,
    tokens_per_second: float | None = 33.0,
    raw_model_output: str | None = None,
) -> TraceRecord:
    triage_json = json.dumps(triage_output) if triage_output else None
    return TraceRecord(
        request_id=request_id,
        run_id=run_id,
        ticket_id=ticket_id,
        timestamp=datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
        model="qwen3.5:4b",
        provider="ollama:qwen3.5:4b",
        prompt_version="v1",
        ticket_body="test",
        guardrail_result="pass",
        validation_status=validation_status,
        retry_count=retry_count,
        latency_ms=latency_ms,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        tokens_total=tokens_total,
        tokens_per_second=tokens_per_second,
        status=status,
        failure_category=failure_category,
        raw_model_output=raw_model_output
        or (json.dumps(triage_output) if triage_output else "bad"),
        triage_output_json=triage_json,
    )


class FakeTraceRepo:
    def __init__(self, traces: list[TraceRecord]):
        self._traces = traces

    def save_trace(self, trace: TraceRecord) -> None:
        self._traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self._traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self._traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self._traces)


class TestSummarizeRunAccuracy:
    def test_all_correct(self):
        trace = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=VALID_OUTPUT,
        )
        repo = FakeTraceRepo([trace])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.category_accuracy == 1.0
        assert metrics.severity_accuracy == 1.0
        assert metrics.routing_accuracy == 1.0
        assert metrics.escalation_accuracy == 1.0

    def test_wrong_category_counts_as_incorrect(self):
        wrong_output = {**VALID_OUTPUT, "category": "network"}
        trace = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=wrong_output,
        )
        repo = FakeTraceRepo([trace])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.category_accuracy == 0.0
        assert metrics.severity_accuracy == 1.0

    def test_failed_trace_counts_as_incorrect_for_all_fields(self):
        trace = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=None,
            status="failure",
            failure_category="parse_failure",
            validation_status="invalid",
        )
        repo = FakeTraceRepo([trace])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.category_accuracy == 0.0
        assert metrics.severity_accuracy == 0.0
        assert metrics.routing_accuracy == 0.0
        assert metrics.escalation_accuracy == 0.0
        assert metrics.successful_tickets == 0

    def test_mixed_correct_and_incorrect(self):
        correct_trace = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=VALID_OUTPUT,
        )
        failed_trace = _make_trace(
            request_id="r2",
            run_id="run-1",
            ticket_id="n-002",
            triage_output=None,
            status="failure",
            failure_category="parse_failure",
            validation_status="invalid",
        )
        repo = FakeTraceRepo([correct_trace, failed_trace])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.category_accuracy == 0.5
        assert metrics.severity_accuracy == 0.5
        assert metrics.total_tickets == 2
        assert metrics.successful_tickets == 1


class TestSummarizeRunReliability:
    def test_json_valid_rate(self):
        valid_trace = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=VALID_OUTPUT,
        )
        invalid_trace = _make_trace(
            request_id="r2",
            run_id="run-1",
            ticket_id="n-002",
            triage_output=None,
            status="failure",
            failure_category="parse_failure",
            validation_status="invalid",
            raw_model_output="not json at all",
        )
        repo = FakeTraceRepo([valid_trace, invalid_trace])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.json_valid_rate == 0.5

    def test_retry_rate_and_success(self):
        no_retry = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=VALID_OUTPUT,
            retry_count=0,
        )
        retry_success = _make_trace(
            request_id="r2",
            run_id="run-1",
            ticket_id="n-002",
            triage_output={
                **VALID_OUTPUT,
                "category": "account_access",
                "severity": "high",
                "routingTeam": "support",
            },
            retry_count=1,
            validation_status="valid_after_retry",
        )
        repo = FakeTraceRepo([no_retry, retry_success])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.retry_rate == 0.5
        assert metrics.retry_success_rate == 1.0

    def test_schema_pass_rate(self):
        valid_trace = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=VALID_OUTPUT,
            validation_status="valid",
        )
        invalid_trace = _make_trace(
            request_id="r2",
            run_id="run-1",
            ticket_id="n-002",
            triage_output=None,
            status="failure",
            failure_category="schema_failure",
            validation_status="invalid",
        )
        repo = FakeTraceRepo([valid_trace, invalid_trace])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.schema_pass_rate == 0.5


class TestSummarizeRunLatency:
    def test_latency_percentiles(self):
        t1 = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=VALID_OUTPUT,
            latency_ms=100.0,
        )
        t2 = _make_trace(
            request_id="r2",
            run_id="run-1",
            ticket_id="n-002",
            triage_output={
                **VALID_OUTPUT,
                "category": "account_access",
                "severity": "high",
                "routingTeam": "support",
            },
            latency_ms=200.0,
        )
        repo = FakeTraceRepo([t1, t2])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.avg_latency_ms == 150.0
        assert metrics.p50_latency_ms == 150.0

    def test_token_averages(self):
        t1 = _make_trace(
            request_id="r1",
            run_id="run-1",
            ticket_id="n-001",
            triage_output=VALID_OUTPUT,
            tokens_input=100,
            tokens_output=50,
            tokens_total=150,
        )
        t2 = _make_trace(
            request_id="r2",
            run_id="run-1",
            ticket_id="n-002",
            triage_output={
                **VALID_OUTPUT,
                "category": "account_access",
                "severity": "high",
                "routingTeam": "support",
            },
            tokens_input=200,
            tokens_output=100,
            tokens_total=300,
        )
        repo = FakeTraceRepo([t1, t2])
        metrics = summarize_run("run-1", TICKETS, repo)
        assert metrics.avg_tokens_input == 150.0
        assert metrics.avg_tokens_output == 75.0
        assert metrics.avg_tokens_total == 225.0


class TestSummarizeRunEdgeCases:
    def test_raises_on_empty_run(self):
        repo = FakeTraceRepo([])
        with pytest.raises(ValueError, match="No traces found"):
            summarize_run("nonexistent", TICKETS, repo)
