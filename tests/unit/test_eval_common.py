from datetime import datetime

from ticket_triage_llm.eval.datasets import GroundTruth, TicketRecord
from ticket_triage_llm.eval.runners.common import run_experiment_pass
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import TraceRecord


VALID_JSON_OUTPUT = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class FakeProvider:
    name: str = "fake:test"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        return ModelResult(
            raw_output=VALID_JSON_OUTPUT,
            model="fake-model",
            latency_ms=100.0,
            tokens_input=50,
            tokens_output=25,
            tokens_total=75,
        )


class FakeTraceRepo:
    def __init__(self):
        self.traces: list[TraceRecord] = []

    def save_trace(self, trace: TraceRecord) -> None:
        self.traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self.traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self.traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self.traces)


TICKETS = [
    TicketRecord(
        id="n-001", subject="Billing issue", body="I have a billing question",
        ground_truth=GroundTruth(
            category="billing", severity="medium",
            routing_team="billing", escalation=False,
        ),
    ),
    TicketRecord(
        id="n-002", subject="Account access", body="Cannot log in",
        ground_truth=GroundTruth(
            category="account_access", severity="high",
            routing_team="support", escalation=False,
        ),
    ),
]


class TestRunExperimentPass:
    def test_returns_one_trace_per_ticket(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS, provider=FakeProvider(), prompt_version="v1",
            trace_repo=repo, run_id="test-run",
        )
        assert len(traces) == 2

    def test_sets_run_id_on_all_traces(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS, provider=FakeProvider(), prompt_version="v1",
            trace_repo=repo, run_id="test-run",
        )
        assert all(t.run_id == "test-run" for t in traces)

    def test_sets_ticket_id_on_all_traces(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS, provider=FakeProvider(), prompt_version="v1",
            trace_repo=repo, run_id="test-run",
        )
        assert traces[0].ticket_id == "n-001"
        assert traces[1].ticket_id == "n-002"

    def test_passes_skip_validation_flag(self):
        repo = FakeTraceRepo()
        traces = run_experiment_pass(
            tickets=TICKETS, provider=FakeProvider(), prompt_version="v1",
            trace_repo=repo, run_id="test-run", skip_validation=True,
        )
        assert all(t.validation_status == "skipped" for t in traces)

    def test_saves_traces_to_repo(self):
        repo = FakeTraceRepo()
        run_experiment_pass(
            tickets=TICKETS, provider=FakeProvider(), prompt_version="v1",
            trace_repo=repo, run_id="test-run",
        )
        assert len(repo.traces) == 2
