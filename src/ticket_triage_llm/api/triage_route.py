"""POST /api/v1/triage — Phase 2."""

from fastapi import APIRouter, HTTPException

from ticket_triage_llm.schemas.trace import TriageResult
from ticket_triage_llm.schemas.triage_input import TriageInput
from ticket_triage_llm.services.provider_router import ProviderRegistry
from ticket_triage_llm.services.triage import run_triage
from ticket_triage_llm.storage.trace_repo import TraceRepository

router = APIRouter(prefix="/api/v1", tags=["triage"])

_registry: ProviderRegistry | None = None
_trace_repo: TraceRepository | None = None
_guardrail_max_length: int = 10_000


def configure(
    registry: ProviderRegistry,
    trace_repo: TraceRepository,
    guardrail_max_length: int = 10_000,
) -> None:
    global _registry, _trace_repo, _guardrail_max_length  # noqa: PLW0603
    _registry = registry
    _trace_repo = trace_repo
    _guardrail_max_length = guardrail_max_length


@router.post("/triage")
def triage_ticket(payload: TriageInput) -> TriageResult:
    if _registry is None or _trace_repo is None:
        raise RuntimeError(
            "API dependencies not configured — call configure() at startup"
        )

    try:
        provider = (
            _registry.get(payload.model) if payload.model else _registry.default()
        )
    except KeyError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider: {payload.model!r}",
        ) from None

    result, _ = run_triage(
        ticket_body=payload.ticket_body,
        ticket_subject=payload.ticket_subject,
        provider=provider,
        prompt_version=payload.prompt_version,
        trace_repo=_trace_repo,
        guardrail_max_length=_guardrail_max_length,
    )
    return result
