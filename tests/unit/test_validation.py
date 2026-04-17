from ticket_triage_llm.schemas.triage_output import TriageOutput
from ticket_triage_llm.services.validation import parse_json, validate_schema

VALID_TRIAGE_JSON = (
    '{"category": "billing", "severity": "medium",'
    ' "routingTeam": "billing", "summary": "Billing issue",'
    ' "businessImpact": "Cannot process payments",'
    ' "draftReply": "We are looking into it.",'
    ' "confidence": 0.85, "escalation": false}'
)


class TestParseJson:
    def test_valid_json_returns_dict(self):
        result = parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_invalid_json_returns_none(self):
        result = parse_json("not json at all")
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_json("")
        assert result is None

    def test_strips_markdown_json_fence(self):
        raw = '```json\n{"key": "value"}\n```'
        result = parse_json(raw)
        assert result == {"key": "value"}

    def test_strips_markdown_fence_without_language(self):
        raw = '```\n{"key": "value"}\n```'
        result = parse_json(raw)
        assert result == {"key": "value"}

    def test_strips_leading_whitespace_before_fence(self):
        raw = '  \n```json\n{"key": "value"}\n```\n  '
        result = parse_json(raw)
        assert result == {"key": "value"}

    def test_valid_json_without_fences(self):
        result = parse_json(VALID_TRIAGE_JSON)
        assert result is not None
        assert result["category"] == "billing"


class TestValidateSchema:
    def test_valid_data_returns_triage_output(self):
        data = {
            "category": "billing",
            "severity": "medium",
            "routingTeam": "billing",
            "summary": "Billing issue",
            "businessImpact": "Cannot process payments",
            "draftReply": "We are looking into it.",
            "confidence": 0.85,
            "escalation": False,
        }
        result = validate_schema(data)
        assert isinstance(result, TriageOutput)
        assert result.category == "billing"

    def test_missing_field_returns_none(self):
        data = {"category": "billing"}
        result = validate_schema(data)
        assert result is None

    def test_invalid_category_returns_none(self):
        data = {
            "category": "unknown_category",
            "severity": "medium",
            "routingTeam": "billing",
            "summary": "Test",
            "businessImpact": "Test",
            "draftReply": "Test",
            "confidence": 0.5,
            "escalation": False,
        }
        result = validate_schema(data)
        assert result is None

    def test_confidence_out_of_range_returns_none(self):
        data = {
            "category": "billing",
            "severity": "medium",
            "routingTeam": "billing",
            "summary": "Test",
            "businessImpact": "Test",
            "draftReply": "Test",
            "confidence": 1.5,
            "escalation": False,
        }
        result = validate_schema(data)
        assert result is None

    def test_accepts_alias_field_names(self):
        data = {
            "category": "bug",
            "severity": "high",
            "routingTeam": "infra",
            "summary": "Bug found",
            "businessImpact": "Service down",
            "draftReply": "Investigating.",
            "confidence": 0.9,
            "escalation": True,
        }
        result = validate_schema(data)
        assert result is not None
        assert result.routing_team == "infra"
