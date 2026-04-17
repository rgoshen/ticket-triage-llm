"""JSON parse, schema validation, semantic checks — Phase 1."""

import json
import re

from pydantic import ValidationError

from ticket_triage_llm.schemas.triage_output import TriageOutput

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


def parse_json(raw_output: str) -> dict | None:
    """Parse JSON from LLM output, stripping markdown fences if present.

    Args:
        raw_output: Raw string from LLM, may include markdown fences

    Returns:
        Parsed dict if valid JSON, None otherwise
    """
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
    """Validate dict against TriageOutput schema.

    Args:
        data: Dict to validate

    Returns:
        TriageOutput instance if valid, None otherwise
    """
    try:
        return TriageOutput.model_validate(data)
    except ValidationError:
        return None


def validate_schema_with_error(data: dict) -> tuple[TriageOutput | None, str | None]:
    """Validate dict against TriageOutput schema, returning error detail.

    Args:
        data: Dict to validate

    Returns:
        Tuple of (TriageOutput instance, None) if valid,
        or (None, error string) if invalid
    """
    try:
        return TriageOutput.model_validate(data), None
    except ValidationError as exc:
        return None, str(exc)
