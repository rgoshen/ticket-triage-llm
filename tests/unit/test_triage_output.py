import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.triage_output import (
    Category,  # noqa: F401
    RoutingTeam,  # noqa: F401
    Severity,  # noqa: F401
    TriageOutput,
)

VALID_OUTPUT = {
    "category": "billing",
    "severity": "high",
    "routingTeam": "billing",
    "summary": "Customer cannot access invoice.",
    "businessImpact": "Billing cycle delayed.",
    "draftReply": "We are looking into your billing issue.",
    "confidence": 0.85,
    "escalation": False,
}


class TestTriageOutput:
    def test_valid_from_camel_case_json(self):
        to = TriageOutput.model_validate(VALID_OUTPUT)
        assert to.category == "billing"
        assert to.routing_team == "billing"
        assert to.business_impact == "Billing cycle delayed."
        assert to.draft_reply == "We are looking into your billing issue."

    def test_valid_from_snake_case(self):
        to = TriageOutput(
            category="outage",
            severity="critical",
            routing_team="infra",
            summary="Service is down.",
            business_impact="Revenue loss.",
            draft_reply="We are investigating.",
            confidence=0.95,
            escalation=True,
        )
        assert to.severity == "critical"

    def test_invalid_category_rejected(self):
        data = {**VALID_OUTPUT, "category": "invalid_category"}
        with pytest.raises(ValidationError, match="category"):
            TriageOutput.model_validate(data)

    def test_invalid_severity_rejected(self):
        data = {**VALID_OUTPUT, "severity": "extreme"}
        with pytest.raises(ValidationError, match="severity"):
            TriageOutput.model_validate(data)

    def test_invalid_routing_team_rejected(self):
        data = {**VALID_OUTPUT, "routingTeam": "marketing"}
        with pytest.raises(ValidationError, match="routingTeam"):
            TriageOutput.model_validate(data)

    def test_confidence_below_zero_rejected(self):
        data = {**VALID_OUTPUT, "confidence": -0.1}
        with pytest.raises(ValidationError, match="confidence"):
            TriageOutput.model_validate(data)

    def test_confidence_above_one_rejected(self):
        data = {**VALID_OUTPUT, "confidence": 1.01}
        with pytest.raises(ValidationError, match="confidence"):
            TriageOutput.model_validate(data)

    def test_confidence_boundary_zero(self):
        data = {**VALID_OUTPUT, "confidence": 0.0}
        to = TriageOutput.model_validate(data)
        assert to.confidence == 0.0

    def test_confidence_boundary_one(self):
        data = {**VALID_OUTPUT, "confidence": 1.0}
        to = TriageOutput.model_validate(data)
        assert to.confidence == 1.0

    def test_missing_required_field_rejected(self):
        data = {k: v for k, v in VALID_OUTPUT.items() if k != "summary"}
        with pytest.raises(ValidationError):
            TriageOutput.model_validate(data)

    def test_round_trip_dump_validate(self):
        to = TriageOutput.model_validate(VALID_OUTPUT)
        dumped = to.model_dump(by_alias=True)
        restored = TriageOutput.model_validate(dumped)
        assert restored == to

    def test_all_categories_accepted(self):
        categories = (
            "billing", "outage", "account_access",
            "bug", "feature_request", "other",
        )
        for cat in categories:
            data = {**VALID_OUTPUT, "category": cat}
            to = TriageOutput.model_validate(data)
            assert to.category == cat

    def test_all_severities_accepted(self):
        for sev in ("low", "medium", "high", "critical"):
            data = {**VALID_OUTPUT, "severity": sev}
            to = TriageOutput.model_validate(data)
            assert to.severity == sev

    def test_all_routing_teams_accepted(self):
        for team in ("support", "billing", "infra", "product", "security"):
            data = {**VALID_OUTPUT, "routingTeam": team}
            to = TriageOutput.model_validate(data)
            assert to.routing_team == team
