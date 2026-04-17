import sqlite3
from datetime import datetime, timezone

import pytest

from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.storage.db import get_connection, init_schema
from ticket_triage_llm.storage.trace_repo import TraceRepository


EXPECTED_COLUMNS = {
    "request_id",
    "run_id",
    "timestamp",
    "model",
    "provider",
    "prompt_version",
    "ticket_body",
    "guardrail_result",
    "guardrail_matched_rules",
    "validation_status",
    "retry_count",
    "latency_ms",
    "tokens_input",
    "tokens_output",
    "tokens_total",
    "tokens_per_second",
    "estimated_cost",
    "status",
    "failure_category",
    "raw_model_output",
    "triage_output_json",
}


class TestInitSchema:
    def test_creates_traces_table(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='traces'"
        )
        assert cursor.fetchone() is not None

    def test_traces_table_has_expected_columns(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)
        cursor = conn.execute("PRAGMA table_info(traces)")
        columns = {row[1] for row in cursor.fetchall()}
        assert columns == EXPECTED_COLUMNS

    def test_idempotent(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)
        init_schema(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='traces'"
        )
        assert cursor.fetchone() is not None

    def test_indexes_created(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='traces'"
        )
        index_names = {row[0] for row in cursor.fetchall()}
        assert "idx_traces_run_id" in index_names
        assert "idx_traces_provider" in index_names
        assert "idx_traces_prompt_version" in index_names
        assert "idx_traces_timestamp" in index_names

    def test_get_connection_returns_sqlite3_connection(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)

    def test_only_traces_table_exists(self, tmp_path):
        """ADR 0005: single traces table, no summary tables."""
        db_path = str(tmp_path / "test.db")
        conn = get_connection(db_path)
        init_schema(conn)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert tables == ["traces"]


class FakeTraceRepository:
    """Minimal fake satisfying the TraceRepository Protocol."""

    def __init__(self) -> None:
        self._traces: list[TraceRecord] = []

    def save_trace(self, trace: TraceRecord) -> None:
        self._traces.append(trace)

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self._traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        return [t for t in self._traces if t.provider == provider]

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        return [t for t in self._traces if t.timestamp >= since]

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return sorted(self._traces, key=lambda t: t.timestamp, reverse=True)[:limit]

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self._traces)


class TestTraceRepositoryProtocol:
    def test_fake_satisfies_protocol(self):
        repo: TraceRepository = FakeTraceRepository()
        assert repo is not None

    def test_save_and_retrieve(self):
        repo: TraceRepository = FakeTraceRepository()
        trace = TraceRecord(
            request_id="test-1",
            timestamp=datetime.now(timezone.utc),
            model="qwen3.5:4b",
            provider="ollama",
            prompt_version="v1",
            ticket_body="test",
            guardrail_result="pass",
            validation_status="valid",
            retry_count=0,
            latency_ms=100.0,
            tokens_input=10,
            tokens_output=20,
            tokens_total=30,
            status="success",
        )
        repo.save_trace(trace)
        assert len(repo.get_all_traces()) == 1
