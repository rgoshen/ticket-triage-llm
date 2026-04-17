from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "billing", "outage", "account_access", "bug", "feature_request", "other"
]

Severity = Literal["low", "medium", "high", "critical"]

RoutingTeam = Literal["support", "billing", "infra", "product", "security"]


class TriageOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: Category
    severity: Severity
    routing_team: RoutingTeam = Field(alias="routingTeam")
    summary: str
    business_impact: str = Field(alias="businessImpact")
    draft_reply: str = Field(alias="draftReply")
    confidence: float = Field(ge=0.0, le=1.0)
    escalation: bool
