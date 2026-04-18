"""JSON parse, schema validation, semantic checks — Phase 1."""

import json
import re

from pydantic import ValidationError

from ticket_triage_llm.schemas.triage_output import TriageOutput

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


def parse_json(raw_output: str) -> dict | None:
    text = raw_output.strip()
    if not text:
        return None

    fence_match = _FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    return data


def validate_schema(data: dict) -> TriageOutput | None:
    try:
        return TriageOutput.model_validate(data)
    except ValidationError:
        return None


def validate_schema_with_error(data: dict) -> tuple[TriageOutput | None, str | None]:
    try:
        return TriageOutput.model_validate(data), None
    except ValidationError as exc:
        return None, str(exc)
