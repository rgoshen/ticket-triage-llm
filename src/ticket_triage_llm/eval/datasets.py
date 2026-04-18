"""Dataset loading for evaluation harness — Phase 3."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GroundTruth:
    category: str
    severity: str
    routing_team: str
    escalation: bool


@dataclass(frozen=True)
class TicketRecord:
    id: str
    subject: str
    body: str
    ground_truth: GroundTruth


def load_dataset(path: Path) -> list[TicketRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    tickets: list[TicketRecord] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            gt = data["ground_truth"]
            tickets.append(
                TicketRecord(
                    id=data["id"],
                    subject=data["subject"],
                    body=data["body"],
                    ground_truth=GroundTruth(
                        category=gt["category"],
                        severity=gt["severity"],
                        routing_team=gt["routing_team"],
                        escalation=gt["escalation"],
                    ),
                )
            )
    return tickets
