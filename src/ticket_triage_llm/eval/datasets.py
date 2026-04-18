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


@dataclass(frozen=True)
class AdversarialTicketRecord:
    id: str
    subject: str
    body: str
    attack_category: str
    expected_behavior: str
    notes: str


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


def load_adversarial_dataset(path: Path) -> list[AdversarialTicketRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    tickets: list[AdversarialTicketRecord] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            tickets.append(
                AdversarialTicketRecord(
                    id=data["id"],
                    subject=data["subject"],
                    body=data["body"],
                    attack_category=data["attack_category"],
                    expected_behavior=data["expected_behavior"],
                    notes=data["notes"],
                )
            )
    return tickets


def adversarial_to_ticket_record(adv: AdversarialTicketRecord) -> TicketRecord:
    return TicketRecord(
        id=adv.id,
        subject=adv.subject,
        body=adv.body,
        ground_truth=GroundTruth(
            category="other",
            severity="medium",
            routing_team="support",
            escalation=False,
        ),
    )
