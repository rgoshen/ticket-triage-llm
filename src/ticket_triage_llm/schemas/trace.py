from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .triage_output import TriageOutput

FailureReason = Literal[
    "guardrail_blocked",
    "model_unreachable",
    "parse_failure",
    "schema_failure",
    "semantic_failure",
]

DetectedBy = Literal["guardrail", "provider", "parser", "schema", "semantic"]


class TriageSuccess(BaseModel):
    status: Literal["success"] = "success"
    output: TriageOutput
    retry_count: int


class TriageFailure(BaseModel):
    status: Literal["failure"] = "failure"
    category: FailureReason
    detected_by: DetectedBy
    message: str
    raw_model_output: str | None = None
    retry_count: int


TriageResult = TriageSuccess | TriageFailure

ValidationStatus = Literal["valid", "valid_after_retry", "invalid", "skipped"]
GuardrailDecision = Literal["pass", "warn", "block"]
TraceStatus = Literal["success", "failure"]


class TraceRecord(BaseModel):
    request_id: str
    run_id: str | None = None
    timestamp: datetime
    model: str
    provider: str
    prompt_version: str
    ticket_body: str
    guardrail_result: GuardrailDecision
    guardrail_matched_rules: list[str] = []
    validation_status: ValidationStatus
    retry_count: int = 0
    latency_ms: float
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    tokens_per_second: float | None = None
    estimated_cost: float = 0.0
    status: TraceStatus
    failure_category: FailureReason | None = None
    raw_model_output: str | None = None
    triage_output_json: str | None = None
