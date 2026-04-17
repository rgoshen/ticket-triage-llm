from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.trace import TraceRecord

VALID_TRACE = {
    "request_id": "abc-123",
    "timestamp": datetime.now(UTC),
    "model": "qwen3.5:4b",
    "provider": "ollama",
    "prompt_version": "v1",
    "ticket_body": "My invoice is wrong",
    "guardrail_result": "pass",
    "validation_status": "valid",
    "retry_count": 0,
    "latency_ms": 1500.0,
    "tokens_input": 150,
    "tokens_output": 200,
    "tokens_total": 350,
    "status": "success",
}


class TestTraceRecord:
    def test_valid_success_trace(self):
        tr = TraceRecord(**VALID_TRACE)
        assert tr.request_id == "abc-123"
        assert tr.run_id is None
        assert tr.failure_category is None
        assert tr.status == "success"

    def test_valid_failure_trace(self):
        tr = TraceRecord(
            **{
                **VALID_TRACE,
                "status": "failure",
                "failure_category": "parse_failure",
                "validation_status": "invalid",
                "raw_model_output": "not json",
            }
        )
        assert tr.failure_category == "parse_failure"
        assert tr.raw_model_output == "not json"

    def test_eval_run_trace_with_run_id(self):
        tr = TraceRecord(**{**VALID_TRACE, "run_id": "exp-001"})
        assert tr.run_id == "exp-001"

    def test_guardrail_blocked_trace(self):
        tr = TraceRecord(
            **{
                **VALID_TRACE,
                "guardrail_result": "block",
                "validation_status": "skipped",
                "status": "failure",
                "failure_category": "guardrail_blocked",
                "latency_ms": 5.0,
                "guardrail_matched_rules": ["injection_phrase:ignore_previous"],
            }
        )
        assert tr.guardrail_result == "block"
        assert tr.guardrail_matched_rules == ["injection_phrase:ignore_previous"]

    def test_invalid_guardrail_result_rejected(self):
        with pytest.raises(ValidationError):
            TraceRecord(**{**VALID_TRACE, "guardrail_result": "maybe"})

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            TraceRecord(**{**VALID_TRACE, "status": "pending"})

    def test_invalid_failure_category_rejected(self):
        with pytest.raises(ValidationError):
            TraceRecord(
                **{
                    **VALID_TRACE,
                    "status": "failure",
                    "failure_category": "unknown_reason",
                }
            )

    def test_defaults(self):
        tr = TraceRecord(**VALID_TRACE)
        assert tr.run_id is None
        assert tr.guardrail_matched_rules == []
        assert tr.tokens_per_second is None
        assert tr.estimated_cost == 0.0
        assert tr.failure_category is None
        assert tr.raw_model_output is None
        assert tr.triage_output_json is None

    def test_round_trip(self):
        tr = TraceRecord(**VALID_TRACE)
        data = tr.model_dump()
        restored = TraceRecord.model_validate(data)
        assert restored == tr
