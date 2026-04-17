from datetime import datetime

from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import (
    TraceRecord,
    TriageFailure,
    TriageSuccess,
)
from ticket_triage_llm.services.triage import run_triage

VALID_JSON_OUTPUT = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class FakeProvider:
    name: str = "fake:test"

    def __init__(self, raw_output: str = VALID_JSON_OUTPUT):
        self._raw_output = raw_output

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        return ModelResult(
            raw_output=self._raw_output,
            model="fake-model",
            latency_ms=100.0,
            tokens_input=50,
            tokens_output=25,
            tokens_total=75,
        )


class ErrorProvider:
    name: str = "error:test"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        raise ProviderError("Connection refused")


class FakeTraceRepo:
    def __init__(self):
        self.traces: list[TraceRecord] = []

    def save_trace(self, trace: TraceRecord) -> None:
        self.traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self.traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        raise NotImplementedError


class TestRunTriageHappyPath:
    def test_returns_triage_success(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="I have a billing question",
            ticket_subject="Billing",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageSuccess)
        assert result.output.category == "billing"
        assert result.retry_count == 0

    def test_saves_trace_on_success(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="I have a billing question",
            ticket_subject="Billing",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert len(repo.traces) == 1
        assert trace.status == "success"
        assert trace.failure_category is None
        assert trace.validation_status == "valid"

    def test_trace_has_request_id(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert trace.request_id is not None
        assert len(trace.request_id) > 0

    def test_returned_trace_matches_saved_trace(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert trace is repo.traces[0]


class TestRunTriageParseFailure:
    def test_returns_triage_failure_on_bad_json(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output="not json"),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "parse_failure"
        assert result.detected_by == "parser"
        assert result.raw_model_output == "not json"

    def test_saves_trace_on_parse_failure(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output="not json"),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert len(repo.traces) == 1
        assert trace.status == "failure"
        assert trace.failure_category == "parse_failure"


class TestRunTriageSchemaFailure:
    def test_returns_triage_failure_on_invalid_schema(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output='{"category": "billing"}'),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "schema_failure"
        assert result.detected_by == "schema"

    def test_saves_trace_on_schema_failure(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=FakeProvider(raw_output='{"category": "billing"}'),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert trace.status == "failure"
        assert trace.failure_category == "schema_failure"


class TestRunTriageProviderError:
    def test_returns_triage_failure_on_provider_error(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=ErrorProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert isinstance(result, TriageFailure)
        assert result.category == "model_unreachable"
        assert result.detected_by == "provider"

    def test_saves_trace_on_provider_error(self):
        repo = FakeTraceRepo()
        result, trace = run_triage(
            ticket_body="test",
            ticket_subject="",
            provider=ErrorProvider(),
            prompt_version="v1",
            trace_repo=repo,
        )
        assert len(repo.traces) == 1
        assert trace.status == "failure"
        assert trace.failure_category == "model_unreachable"
