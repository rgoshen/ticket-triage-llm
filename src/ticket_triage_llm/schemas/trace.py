from __future__ import annotations

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
