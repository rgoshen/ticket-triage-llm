import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.errors import assert_never_failure_reason
from ticket_triage_llm.schemas.trace import (
    FailureReason,
    TriageFailure,
    TriageResult,
    TriageSuccess,
)
from ticket_triage_llm.schemas.triage_output import TriageOutput

VALID_OUTPUT = TriageOutput(
    category="billing",
    severity="high",
    routing_team="billing",
    summary="Invoice issue.",
    business_impact="Delayed cycle.",
    draft_reply="Looking into it.",
    confidence=0.85,
    escalation=False,
)

ALL_FAILURE_REASONS: list[FailureReason] = [
    "guardrail_blocked",
    "model_unreachable",
    "parse_failure",
    "schema_failure",
    "semantic_failure",
]


class TestTriageSuccess:
    def test_construction(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=0)
        assert ts.status == "success"
        assert ts.output.category == "billing"
        assert ts.retry_count == 0

    def test_status_is_always_success(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=1)
        assert ts.status == "success"

    def test_round_trip(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=1)
        data = ts.model_dump(by_alias=True)
        assert data["status"] == "success"
        restored = TriageSuccess.model_validate(data)
        assert restored.output.category == "billing"


class TestTriageFailure:
    def test_construction(self):
        tf = TriageFailure(
            category="parse_failure",
            detected_by="parser",
            message="Invalid JSON",
            retry_count=1,
        )
        assert tf.status == "failure"
        assert tf.category == "parse_failure"
        assert tf.detected_by == "parser"
        assert tf.raw_model_output is None

    def test_with_raw_output(self):
        tf = TriageFailure(
            category="schema_failure",
            detected_by="schema",
            message="Missing field: severity",
            raw_model_output='{"category": "billing"}',
            retry_count=1,
        )
        assert tf.raw_model_output == '{"category": "billing"}'

    def test_invalid_category_rejected(self):
        with pytest.raises(ValidationError):
            TriageFailure(
                category="unknown_failure",  # type: ignore[arg-type]
                detected_by="parser",
                message="test",
                retry_count=0,
            )

    def test_invalid_detected_by_rejected(self):
        with pytest.raises(ValidationError):
            TriageFailure(
                category="parse_failure",
                detected_by="unknown_layer",  # type: ignore[arg-type]
                message="test",
                retry_count=0,
            )

    def test_all_failure_reasons_accepted(self):
        detected_by_map = {
            "guardrail_blocked": "guardrail",
            "model_unreachable": "provider",
            "parse_failure": "parser",
            "schema_failure": "schema",
            "semantic_failure": "semantic",
        }
        for reason in ALL_FAILURE_REASONS:
            tf = TriageFailure(
                category=reason,
                detected_by=detected_by_map[reason],
                message=f"Failed: {reason}",
                retry_count=0,
            )
            assert tf.category == reason


class TestTriageResult:
    def test_success_discriminates(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=0)
        result: TriageResult = ts
        assert isinstance(result, TriageSuccess)

    def test_failure_discriminates(self):
        tf = TriageFailure(
            category="parse_failure",
            detected_by="parser",
            message="bad json",
            retry_count=1,
        )
        result: TriageResult = tf
        assert isinstance(result, TriageFailure)

    def test_success_dump_and_validate_round_trip(self):
        ts = TriageSuccess(output=VALID_OUTPUT, retry_count=0)
        data = ts.model_dump(by_alias=True)
        assert data["status"] == "success"

    def test_failure_dump_and_validate_round_trip(self):
        tf = TriageFailure(
            category="guardrail_blocked",
            detected_by="guardrail",
            message="Injection detected",
            retry_count=0,
        )
        data = tf.model_dump()
        assert data["status"] == "failure"
        restored = TriageFailure.model_validate(data)
        assert restored.category == "guardrail_blocked"


class TestAssertNeverFailureReason:
    def test_raises_on_unknown_value(self):
        with pytest.raises(AssertionError, match="Unhandled failure reason"):
            assert_never_failure_reason("not_a_real_reason")  # type: ignore[arg-type]

    def test_all_known_reasons_documented(self):
        assert len(ALL_FAILURE_REASONS) == 5
