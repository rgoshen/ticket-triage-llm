from tests.fakes import FakeProvider, FakeTraceRepo
from ticket_triage_llm.eval.datasets import GroundTruth, TicketRecord
from ticket_triage_llm.eval.runners.common import run_experiment_pass

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


class TestRunExperimentPass:
    def test_returns_one_trace_per_ticket(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert len(traces) == 2

    def test_sets_run_id_on_all_traces(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert all(t.run_id == "test-run" for t in traces)

    def test_sets_ticket_id_on_all_traces(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert traces[0].ticket_id == "n-001"
        assert traces[1].ticket_id == "n-002"

    def test_passes_skip_validation_flag(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
            skip_validation=True,
        )
        assert all(t.validation_status == "skipped" for t in traces)

    def test_saves_traces_to_repo(self):
        repo = FakeTraceRepo()
        run_experiment_pass(
            tickets=TICKETS,
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
            run_id="test-run",
        )
        assert len(repo.traces) == 2
