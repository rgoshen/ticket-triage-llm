import sqlite3
from datetime import UTC, datetime

import pytest

from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.storage.db import get_connection, init_schema
from ticket_triage_llm.storage.trace_repo import TraceRepository

EXPECTED_COLUMNS = {
    "request_id",
    "run_id",
    "ticket_id",
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
        assert "idx_traces_ticket_id" in index_names
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
            "SELECT name FROM sqlite_master"
            " WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert tables == ["traces"]


class TestCheckConstraints:
    """CHECK constraints mirror the Literal types in TraceRecord."""

    def _insert_trace(self, conn, **overrides):
        defaults = {
            "request_id": "chk-1",
            "timestamp": "2026-04-17T00:00:00Z",
            "model": "qwen3.5:4b",
            "provider": "ollama",
            "prompt_version": "v1",
            "ticket_body": "test",
            "guardrail_result": "pass",
            "validation_status": "valid",
            "retry_count": 0,
            "latency_ms": 100.0,
            "status": "success",
            "failure_category": None,
        }
        defaults.update(overrides)
        cols = ", ".join(defaults.keys())
        placeholders = ", ".join("?" for _ in defaults)
        conn.execute(
            f"INSERT INTO traces ({cols}) VALUES ({placeholders})",
            list(defaults.values()),
        )

    def test_valid_success_row_accepted(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        self._insert_trace(conn)
        assert conn.execute("SELECT count(*) FROM traces").fetchone()[0] == 1

    def test_invalid_guardrail_result_rejected(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_trace(conn, guardrail_result="maybe")

    def test_invalid_validation_status_rejected(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_trace(conn, validation_status="unknown")

    def test_invalid_status_rejected(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_trace(conn, status="pending")

    def test_invalid_failure_category_rejected(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_trace(
                conn,
                status="failure",
                failure_category="unknown_reason",
            )

    def test_success_with_failure_category_rejected(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_trace(
                conn,
                status="success",
                failure_category="parse_failure",
            )

    def test_failure_without_failure_category_rejected(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        with pytest.raises(sqlite3.IntegrityError):
            self._insert_trace(
                conn,
                status="failure",
                failure_category=None,
            )

    def test_valid_failure_row_accepted(self, tmp_path):
        conn = get_connection(str(tmp_path / "t.db"))
        init_schema(conn)
        self._insert_trace(
            conn,
            request_id="chk-2",
            status="failure",
            failure_category="parse_failure",
        )
        assert conn.execute("SELECT count(*) FROM traces").fetchone()[0] == 1


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
            timestamp=datetime.now(UTC),
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
