from ticket_triage_llm.providers.errors import ProviderError
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import TriageFailure, TriageSuccess
from ticket_triage_llm.services.retry import validate_or_retry

VALID_JSON = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class SequenceProvider:
    """Provider that returns a sequence of raw outputs, one per call."""

    def __init__(self, outputs: list[str]):
        self.name = "fake:sequence"
        self._outputs = list(outputs)
        self._call_count = 0

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        raw = self._outputs[self._call_count]
        self._call_count += 1
        return ModelResult(
            raw_output=raw,
            model="fake",
            latency_ms=50.0,
            tokens_input=10,
            tokens_output=10,
            tokens_total=20,
        )


class ErrorOnRetryProvider:
    """Provider that raises ProviderError on the second call (retry)."""

    name = "fake:error-on-retry"

    def __init__(self):
        self._call_count = 0

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        self._call_count += 1
        if self._call_count >= 1:
            raise ProviderError("Connection lost during retry")
        return ModelResult(
            raw_output="not json",
            model="fake",
            latency_ms=50.0,
            tokens_input=10,
            tokens_output=10,
            tokens_total=20,
        )


class TestFirstAttemptSuccess:
    def test_valid_output_no_retry(self):
        result = validate_or_retry(
            raw_output=VALID_JSON,
            provider=SequenceProvider([]),
            prompt_version="v1",
            ticket_subject="",
            ticket_body="test ticket",
        )
        assert isinstance(result.result, TriageSuccess)
        assert result.retry_count == 0
        assert result.result.output.category == "billing"


class TestParseFailureRetry:
    def test_parse_fail_then_repair_succeeds(self):
        provider = SequenceProvider([VALID_JSON])
        result = validate_or_retry(
            raw_output="not json at all",
            provider=provider,
            prompt_version="v1",
            ticket_subject="",
            ticket_body="test ticket",
        )
        assert isinstance(result.result, TriageSuccess)
        assert result.retry_count == 1

    def test_parse_fail_then_repair_also_fails(self):
        provider = SequenceProvider(["still not json"])
        result = validate_or_retry(
            raw_output="not json",
            provider=provider,
            prompt_version="v1",
            ticket_subject="",
            ticket_body="test ticket",
        )
        assert isinstance(result.result, TriageFailure)
        assert result.result.category == "parse_failure"
        assert result.retry_count == 1


class TestSchemaFailureRetry:
    def test_schema_fail_then_repair_succeeds(self):
        provider = SequenceProvider([VALID_JSON])
        result = validate_or_retry(
            raw_output='{"category": "billing"}',
            provider=provider,
            prompt_version="v1",
            ticket_subject="",
            ticket_body="test ticket",
        )
        assert isinstance(result.result, TriageSuccess)
        assert result.retry_count == 1

    def test_schema_fail_then_repair_also_fails(self):
        provider = SequenceProvider(['{"category": "billing"}'])
        result = validate_or_retry(
            raw_output='{"category": "billing"}',
            provider=provider,
            prompt_version="v1",
            ticket_subject="",
            ticket_body="test ticket",
        )
        assert isinstance(result.result, TriageFailure)
        assert result.result.category == "schema_failure"
        assert result.retry_count == 1


class TestProviderErrorDuringRetry:
    def test_provider_error_on_retry(self):
        provider = ErrorOnRetryProvider()
        result = validate_or_retry(
            raw_output="not json",
            provider=provider,
            prompt_version="v1",
            ticket_subject="",
            ticket_body="test ticket",
        )
        assert isinstance(result.result, TriageFailure)
        assert result.result.category == "model_unreachable"
        assert result.retry_count == 1
