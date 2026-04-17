"""POST /api/v1/triage — Phase 1."""

from fastapi import APIRouter

from ticket_triage_llm.providers.base import LlmProvider
from ticket_triage_llm.schemas.trace import TriageResult
from ticket_triage_llm.schemas.triage_input import TriageInput
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository

router = APIRouter(prefix="/api/v1", tags=["triage"])

_provider: LlmProvider | None = None
_trace_repo: TraceRepository | None = None


def configure(provider: LlmProvider, trace_repo: TraceRepository) -> None:
    global _provider, _trace_repo  # noqa: PLW0603
    _provider = provider
    _trace_repo = trace_repo


@router.post("/triage")
def triage_ticket(payload: TriageInput) -> TriageResult:
    assert _provider is not None, "Provider not configured"
    assert _trace_repo is not None, "TraceRepository not configured"

    return run_triage(
        ticket_body=payload.ticket_body,
        ticket_subject=payload.ticket_subject,
        provider=_provider,
        prompt_version=payload.prompt_version,
        trace_repo=_trace_repo,
    )
