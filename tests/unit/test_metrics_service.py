from datetime import UTC, datetime

import pytest

from tests.fakes import FakeTraceRepo
from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.services.metrics import (
    get_live_summary,
    group_runs_by_experiment,
    list_run_ids,
)


def _make_trace(**overrides) -> TraceRecord:
    defaults = {
        "request_id": "req-001",
        "timestamp": datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
        "model": "qwen3.5:4b",
        "provider": "ollama:qwen3.5:4b",
        "prompt_version": "v1",
        "ticket_body": "Test ticket",
        "guardrail_result": "pass",
        "validation_status": "valid",
        "retry_count": 0,
        "latency_ms": 1500.0,
        "tokens_input": 100,
        "tokens_output": 50,
        "tokens_total": 150,
        "status": "success",
    }
    defaults.update(overrides)
    return TraceRecord(**defaults)


class TestListRunIds:
    def test_returns_run_ids_from_repo(self):
        repo = FakeTraceRepo(
            [
                _make_trace(request_id="r1", run_id="e1-4b-20260417"),
                _make_trace(request_id="r2", run_id="e1-4b-20260417"),
                _make_trace(request_id="r3", run_id="e1-9b-20260417"),
            ]
        )
        result = list_run_ids(repo)
        assert len(result) == 2
        run_ids = {r["run_id"] for r in result}
        assert run_ids == {"e1-4b-20260417", "e1-9b-20260417"}

    def test_returns_empty_when_no_runs(self):
        repo = FakeTraceRepo([_make_trace(request_id="r1", run_id=None)])
        result = list_run_ids(repo)
        assert result == []


class TestGetLiveSummary:
    def test_computes_stats_from_live_traffic(self):
        repo = FakeTraceRepo(
            [
                _make_trace(
                    request_id="r1",
                    run_id=None,
                    latency_ms=1000.0,
                    status="success",
                    retry_count=0,
                ),
                _make_trace(
                    request_id="r2",
                    run_id=None,
                    latency_ms=2000.0,
                    status="success",
                    retry_count=1,
                ),
                _make_trace(
                    request_id="r3",
                    run_id=None,
                    latency_ms=3000.0,
                    status="failure",
                    failure_category="parse_failure",
                    retry_count=0,
                ),
            ]
        )
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 3
        assert result["success_rate"] == pytest.approx(2 / 3)
        assert result["error_rate"] == pytest.approx(1 / 3)
        assert result["retry_rate"] == pytest.approx(1 / 3)
        assert result["avg_latency_ms"] == pytest.approx(2000.0)

    def test_excludes_eval_traffic(self):
        repo = FakeTraceRepo(
            [
                _make_trace(request_id="r1", run_id=None, latency_ms=1000.0),
                _make_trace(request_id="r2", run_id="e1-4b-20260417", latency_ms=500.0),
            ]
        )
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 1
        assert result["avg_latency_ms"] == pytest.approx(1000.0)

    def test_returns_zeros_when_no_live_traffic(self):
        repo = FakeTraceRepo(
            [
                _make_trace(request_id="r1", run_id="e1-4b-20260417"),
            ]
        )
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 0
        assert result["success_rate"] == 0.0
        assert result["avg_latency_ms"] == 0.0

    def test_respects_window_hours(self):
        repo = FakeTraceRepo(
            [
                _make_trace(
                    request_id="old",
                    run_id=None,
                    timestamp=datetime(2026, 4, 16, 0, 0, 0, tzinfo=UTC),
                    latency_ms=5000.0,
                ),
                _make_trace(
                    request_id="recent",
                    run_id=None,
                    timestamp=datetime(2026, 4, 17, 23, 0, 0, tzinfo=UTC),
                    latency_ms=1000.0,
                ),
            ]
        )
        result = get_live_summary(repo, window_hours=None)
        assert result["total_requests"] == 2


class TestGroupRunsByExperiment:
    def test_groups_by_prefix(self):
        run_ids = [
            {
                "run_id": "e1-4b-20260417",
                "model": "qwen3.5:4b",
                "timestamp": "2026-04-17",
                "ticket_count": 35,
            },
            {
                "run_id": "e1-9b-20260417",
                "model": "qwen3.5:9b",
                "timestamp": "2026-04-17",
                "ticket_count": 35,
            },
            {
                "run_id": "e3-4b-validated-20260417",
                "model": "qwen3.5:4b",
                "timestamp": "2026-04-17",
                "ticket_count": 35,
            },
            {
                "run_id": "adv-4b-20260418",
                "model": "qwen3.5:4b",
                "timestamp": "2026-04-18",
                "ticket_count": 14,
            },
        ]
        result = group_runs_by_experiment(run_ids)
        assert "E1: Model Size Comparison" in result
        assert len(result["E1: Model Size Comparison"]) == 2
        assert "E3: Validation Impact" in result
        assert len(result["E3: Validation Impact"]) == 1
        assert "Adversarial: Injection Defense" in result
        assert len(result["Adversarial: Injection Defense"]) == 1

    def test_unknown_prefix_grouped_as_other(self):
        run_ids = [
            {
                "run_id": "custom-run-123",
                "model": "qwen3.5:4b",
                "timestamp": "2026-04-17",
                "ticket_count": 10,
            },
        ]
        result = group_runs_by_experiment(run_ids)
        assert "Other" in result

    def test_empty_input(self):
        result = group_runs_by_experiment([])
        assert result == {}
