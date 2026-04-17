import json
from datetime import UTC, datetime

import pytest

from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.services.trace import SqliteTraceRepository
from ticket_triage_llm.storage.db import get_connection, init_schema


def _make_trace(**overrides) -> TraceRecord:
    defaults = {
        "request_id": "req-001",
        "timestamp": datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
        "model": "qwen3.5:4b",
        "provider": "ollama:qwen3.5:4b",
        "prompt_version": "v1",
        "ticket_body": "My printer is broken",
        "guardrail_result": "pass",
        "guardrail_matched_rules": [],
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


@pytest.fixture()
def repo(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    init_schema(conn)
    return SqliteTraceRepository(conn)


class TestSaveTrace:
    def test_save_and_count(self, repo):
        trace = _make_trace()
        repo.save_trace(trace)
        rows = repo._conn.execute("SELECT count(*) FROM traces").fetchone()
        assert rows[0] == 1

    def test_save_stores_correct_fields(self, repo):
        trace = _make_trace(
            request_id="req-fields",
            model="qwen3.5:9b",
            latency_ms=2000.0,
        )
        repo.save_trace(trace)
        row = repo._conn.execute(
            "SELECT model, latency_ms FROM traces WHERE request_id = ?",
            ("req-fields",),
        ).fetchone()
        assert row[0] == "qwen3.5:9b"
        assert row[1] == 2000.0

    def test_save_serializes_matched_rules_as_json(self, repo):
        trace = _make_trace(
            request_id="req-rules",
            guardrail_matched_rules=["rule_a", "rule_b"],
        )
        repo.save_trace(trace)
        row = repo._conn.execute(
            "SELECT guardrail_matched_rules FROM traces WHERE request_id = ?",
            ("req-rules",),
        ).fetchone()
        assert json.loads(row[0]) == ["rule_a", "rule_b"]

    def test_save_failure_trace(self, repo):
        trace = _make_trace(
            request_id="req-fail",
            status="failure",
            failure_category="parse_failure",
            validation_status="invalid",
        )
        repo.save_trace(trace)
        row = repo._conn.execute(
            "SELECT status, failure_category FROM traces WHERE request_id = ?",
            ("req-fail",),
        ).fetchone()
        assert row[0] == "failure"
        assert row[1] == "parse_failure"


class TestGetRecentTraces:
    def test_returns_traces_newest_first(self, repo):
        repo.save_trace(
            _make_trace(
                request_id="old",
                timestamp=datetime(2026, 4, 17, 10, 0, 0, tzinfo=UTC),
            )
        )
        repo.save_trace(
            _make_trace(
                request_id="new",
                timestamp=datetime(2026, 4, 17, 12, 0, 0, tzinfo=UTC),
            )
        )
        traces = repo.get_recent_traces(10)
        assert len(traces) == 2
        assert traces[0].request_id == "new"
        assert traces[1].request_id == "old"

    def test_respects_limit(self, repo):
        for i in range(5):
            repo.save_trace(
                _make_trace(
                    request_id=f"req-{i}",
                    timestamp=datetime(2026, 4, 17, i, 0, 0, tzinfo=UTC),
                )
            )
        traces = repo.get_recent_traces(2)
        assert len(traces) == 2

    def test_returns_empty_list_when_no_traces(self, repo):
        traces = repo.get_recent_traces(10)
        assert traces == []

    def test_round_trip_preserves_data(self, repo):
        original = _make_trace(
            request_id="rt-1",
            tokens_per_second=33.5,
            triage_output_json='{"category": "billing"}',
        )
        repo.save_trace(original)
        retrieved = repo.get_recent_traces(1)[0]
        assert retrieved.request_id == "rt-1"
        assert retrieved.model == "qwen3.5:4b"
        assert retrieved.tokens_per_second == 33.5
        assert retrieved.triage_output_json == '{"category": "billing"}'


class TestTicketId:
    def test_save_and_retrieve_ticket_id(self, repo):
        trace = _make_trace(request_id="req-ticket", ticket_id="n-042")
        repo.save_trace(trace)
        retrieved = repo.get_recent_traces(1)[0]
        assert retrieved.ticket_id == "n-042"

    def test_ticket_id_defaults_to_none(self, repo):
        trace = _make_trace(request_id="req-no-ticket")
        repo.save_trace(trace)
        retrieved = repo.get_recent_traces(1)[0]
        assert retrieved.ticket_id is None


class TestUnimplementedMethods:
    def test_get_traces_by_run_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_traces_by_run("run-1")

    def test_get_traces_by_provider_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_traces_by_provider("ollama")

    def test_get_traces_since_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_traces_since(datetime.now(UTC))

    def test_get_all_traces_raises(self, repo):
        with pytest.raises(NotImplementedError):
            repo.get_all_traces()
