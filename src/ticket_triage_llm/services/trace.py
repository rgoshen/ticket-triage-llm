"""Trace recording and retrieval — Phase 1."""

import json
import sqlite3
from datetime import datetime

from ticket_triage_llm.schemas.trace import TraceRecord


class SqliteTraceRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_trace(self, trace: TraceRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO traces (
                request_id, run_id, ticket_id, timestamp, model, provider,
                prompt_version, ticket_body, guardrail_result,
                guardrail_matched_rules, validation_status, retry_count,
                latency_ms, tokens_input, tokens_output, tokens_total,
                tokens_per_second, estimated_cost, status,
                failure_category, raw_model_output, triage_output_json
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                trace.request_id,
                trace.run_id,
                trace.ticket_id,
                trace.timestamp.isoformat(),
                trace.model,
                trace.provider,
                trace.prompt_version,
                trace.ticket_body,
                trace.guardrail_result,
                json.dumps(trace.guardrail_matched_rules),
                trace.validation_status,
                trace.retry_count,
                trace.latency_ms,
                trace.tokens_input,
                trace.tokens_output,
                trace.tokens_total,
                trace.tokens_per_second,
                trace.estimated_cost,
                trace.status,
                trace.failure_category,
                trace.raw_model_output,
                trace.triage_output_json,
            ),
        )
        self._conn.commit()

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [self._row_to_trace(columns, row) for row in rows]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM traces WHERE run_id = ? ORDER BY timestamp",
            (run_id,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [self._row_to_trace(columns, row) for row in rows]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError("get_traces_by_provider: Phase 5")

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError("get_traces_since: Phase 5")

    def get_all_traces(self) -> list[TraceRecord]:
        cursor = self._conn.execute(
            "SELECT * FROM traces ORDER BY timestamp DESC",
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [self._row_to_trace(columns, row) for row in rows]

    @staticmethod
    def _row_to_trace(columns: list[str], row: tuple) -> TraceRecord:
        data = dict(zip(columns, row, strict=True))
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["guardrail_matched_rules"] = json.loads(data["guardrail_matched_rules"])
        return TraceRecord.model_validate(data)
