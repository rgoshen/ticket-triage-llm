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


class TestUnknownTicketIdLogging:
    """I7 regression: unknown ticket_id is bucketed as 'unknown' but a warning
    is emitted once per unseen ID so operators can investigate orphan traces.
    """

    def test_unknown_ticket_id_emits_warning(self, caplog):
        """Construct a trace whose ticket_id isn't in ticket_categories.

        Before the I7 fix, it was silently bucketed as 'unknown' with no
        log signal. The fix emits a warning per distinct unknown id.
        """
        import logging

        from ticket_triage_llm.eval.runners.run_adversarial_eval import (
            _compute_per_rule_stats,
        )

        orphan_trace = _make_success_trace(
            "a-999-orphan",
            run_id="test-run",
            triage_output_json=(
                '{"category": "other", "severity": "low",'
                ' "routingTeam": "support", "summary": "X",'
                ' "businessImpact": "X", "draftReply": "X",'
                ' "confidence": 0.9, "escalation": false}'
            ),
        )
        # Give the trace a guardrail rule match so it appears in the stats
        orphan_trace = orphan_trace.model_copy(
            update={"guardrail_matched_rules": ["test_rule"]}
        )
        # Another trace for the SAME orphan id - to verify warn-once behavior
        orphan_trace_2 = orphan_trace.model_copy(update={"request_id": "req-2"})

        ticket_categories = {"a-001": "direct_injection"}

        with caplog.at_level(logging.WARNING):
            hits, rule_cats = _compute_per_rule_stats(
                [orphan_trace, orphan_trace_2],
                ticket_categories,
            )

        # Stats should still compute correctly
        assert hits == {"test_rule": 2}
        assert rule_cats == {"test_rule": ["unknown"]}

        # Exactly one warning for the repeated unknown id (not two)
        warnings = [r for r in caplog.records if "a-999-orphan" in r.getMessage()]
        assert len(warnings) == 1, (
            f"Expected exactly one warning for repeated unknown id, got {len(warnings)}"
        )
