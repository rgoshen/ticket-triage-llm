from fastapi import FastAPI
from fastapi.testclient import TestClient

from ticket_triage_llm.api.triage_route import configure, router
from ticket_triage_llm.schemas.model_result import ModelResult
from ticket_triage_llm.schemas.trace import TraceRecord
from ticket_triage_llm.services.provider_router import ProviderRegistry

VALID_JSON = (
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
            raw_output=VALID_JSON,
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
        raise NotImplementedError

    def get_traces_by_provider(self, provider: str) -> list[TraceRecord]:
        raise NotImplementedError

    def get_traces_since(self, since) -> list[TraceRecord]:
        raise NotImplementedError

    def get_all_traces(self) -> list[TraceRecord]:
        raise NotImplementedError


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    registry = ProviderRegistry()
    registry.register(FakeProvider())
    configure(registry, FakeTraceRepo())
    return test_app


class TestTriageEndpoint:
    def test_happy_path_returns_200(self):
        client = TestClient(_build_test_app())
        response = client.post(
            "/api/v1/triage",
            json={
                "ticket_body": "I have a billing question",
                "ticket_subject": "Billing",
            },
        )
        assert response.status_code == 200

    def test_happy_path_returns_success_status(self):
        client = TestClient(_build_test_app())
        response = client.post(
            "/api/v1/triage",
            json={"ticket_body": "I have a billing question"},
        )
        data = response.json()
        assert data["status"] == "success"
        assert data["output"]["category"] == "billing"

    def test_empty_body_returns_422(self):
        client = TestClient(_build_test_app())
        response = client.post(
            "/api/v1/triage",
            json={"ticket_body": "   "},
        )
        assert response.status_code == 422
