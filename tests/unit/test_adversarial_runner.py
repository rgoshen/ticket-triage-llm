"""Regression tests for run_adversarial_eval robustness.

Covers latent bug I2: a single corrupt trace row used to crash the entire
multi-model adversarial pass because TriageOutput.model_validate_json was
called without error handling. The fix reconstructs the compliance check
as a schema_failure and logs a warning; the pass continues.
"""

from datetime import UTC, datetime

from tests.fakes import FakeProvider, FakeTraceRepo
from ticket_triage_llm.eval.datasets import (
    AdversarialTicketRecord,
    GroundTruth,
    TicketRecord,
)
from ticket_triage_llm.eval.runners.run_adversarial_eval import (
    run_adversarial_eval,
)
from ticket_triage_llm.schemas.trace import TraceRecord


def _make_adversarial_ticket(
    ticket_id: str, body: str = "Adversarial"
) -> AdversarialTicketRecord:
    return AdversarialTicketRecord(
        id=ticket_id,
        subject="",
        body=body,
        attack_category="direct_injection",
        expected_behavior="resist",
        notes="",
    )


def _make_normal_ticket(ticket_id: str = "n-001") -> TicketRecord:
    return TicketRecord(
        id=ticket_id,
        subject="",
        body="Normal ticket",
        ground_truth=GroundTruth(
            category="billing",
            severity="low",
            routing_team="billing",
            escalation=False,
        ),
    )


def _make_success_trace(
    ticket_id: str,
    run_id: str,
    triage_output_json: str,
    model: str = "fake:test",
) -> TraceRecord:
    return TraceRecord(
        request_id=f"req-{ticket_id}",
        ticket_id=ticket_id,
        run_id=run_id,
        timestamp=datetime.now(UTC),
        model=model,
        provider=model,
        prompt_version="v1",
        ticket_body="any body",
        guardrail_result="pass",
        guardrail_matched_rules=[],
        validation_status="valid",
        retry_count=0,
        latency_ms=100.0,
        tokens_input=50,
        tokens_output=25,
        tokens_total=75,
        status="success",
        failure_category=None,
        raw_model_output=None,
        triage_output_json=triage_output_json,
    )


class TestCorruptTraceHandling:
    """I2 regression: a corrupt trace must not crash the adversarial pass."""

    def test_corrupt_trace_does_not_crash_pass(self, monkeypatch):
        """Simulate a trace with malformed triage_output_json among good ones.

        Before the I2 fix, TriageOutput.model_validate_json raised
        pydantic.ValidationError and the outer provider loop propagated the
        exception. The fix catches any Exception, logs a warning, and
        reconstructs the compliance check as schema_failure.
        """
        from ticket_triage_llm.eval.runners import run_adversarial_eval as module

        adv_tickets = [
            _make_adversarial_ticket("a-001"),
            _make_adversarial_ticket("a-002"),
        ]
        normal_tickets = [_make_normal_ticket()]

        good_trace = _make_success_trace(
            "a-001",
            run_id="test-run",
            triage_output_json=(
                '{"category": "billing", "severity": "low",'
                ' "routingTeam": "billing", "summary": "X",'
                ' "businessImpact": "X", "draftReply": "X",'
                ' "confidence": 0.9, "escalation": false}'
            ),
        )
        corrupt_trace = _make_success_trace(
            "a-002",
            run_id="test-run",
            triage_output_json="{not valid json at all",
        )

        def fake_run_pass(**kwargs):
            return [good_trace, corrupt_trace]

        monkeypatch.setattr(module, "run_experiment_pass", fake_run_pass)

        provider = FakeProvider()
        repo = FakeTraceRepo()

        # Must not raise.
        summaries = run_adversarial_eval(
            providers=[provider],
            adv_tickets=adv_tickets,
            normal_tickets=normal_tickets,
            trace_repo=repo,
            run_suffix="test",
        )

        assert len(summaries) == 1
        summary = summaries[0]
        # Both tickets must appear in compliance_checks - the corrupt one
        # reconstructed as a schema_failure rather than dropped.
        check_ids = {c["ticket_id"] for c in summary.compliance_checks}
        assert "a-001" in check_ids
        assert "a-002" in check_ids
