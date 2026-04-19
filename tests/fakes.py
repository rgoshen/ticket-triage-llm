"""Shared test fakes for unit tests."""

from datetime import datetime

from ticket_triage_llm.providers.errors import ProviderError
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


class FakeTraceRepo:
    def __init__(self, traces: list[TraceRecord] | None = None):
        self.traces: list[TraceRecord] = list(traces) if traces else []

    def save_trace(self, trace: TraceRecord) -> None:
        self.traces.append(trace)

    def get_recent_traces(self, limit: int) -> list[TraceRecord]:
        return self.traces[:limit]

    def get_traces_by_run(self, run_id: str) -> list[TraceRecord]:
        return [t for t in self.traces if t.run_id == run_id]

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        return [t for t in self.traces if t.provider == provider]

    def get_traces_since(self, since: datetime) -> list[TraceRecord]:
        return [t for t in self.traces if t.timestamp >= since]

    def get_all_traces(self) -> list[TraceRecord]:
        return list(self.traces)

    def get_distinct_run_ids(self) -> list[dict]:
        runs: dict[str, dict] = {}
        for t in self.traces:
            if t.run_id is None:
                continue
            if t.run_id not in runs:
                runs[t.run_id] = {
                    "run_id": t.run_id,
                    "model": t.model,
                    "timestamp": t.timestamp.isoformat(),
                    "ticket_count": 0,
                }
            runs[t.run_id]["ticket_count"] += 1
        return sorted(runs.values(), key=lambda r: r["timestamp"], reverse=True)


class AlwaysBadJsonProvider:
    """Always returns invalid JSON, even on retry."""

    name: str = "fake:always-bad-json"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        return ModelResult(
            raw_output="not json at all",
            model="fake-model",
            latency_ms=100.0,
            tokens_input=50,
            tokens_output=25,
            tokens_total=75,
        )


class AlwaysBadSchemaProvider:
    """Always returns JSON that fails schema validation."""

    name: str = "fake:always-bad-schema"

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        return ModelResult(
            raw_output='{"category": "billing"}',
            model="fake-model",
            latency_ms=100.0,
            tokens_input=50,
            tokens_output=25,
            tokens_total=75,
        )


class RetrySuccessProvider:
    """Returns invalid JSON first, then valid JSON on retry."""

    name: str = "fake:retry-success"

    def __init__(self):
        self._call_count = 0

    def generate_structured_ticket(
        self, ticket_body: str, prompt_version: str, ticket_subject: str = ""
    ) -> ModelResult:
        self._call_count += 1
        raw = VALID_JSON_OUTPUT if self._call_count > 1 else "not json"
        return ModelResult(
            raw_output=raw,
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
