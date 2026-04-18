"""Unit tests for adversarial dataset loading — Phase 4 Task 1."""

import json
from pathlib import Path

import pytest

from ticket_triage_llm.eval.datasets import (
    AdversarialTicketRecord,
    GroundTruth,
    TicketRecord,
    adversarial_to_ticket_record,
    load_adversarial_dataset,
)


def test_load_adversarial_dataset_single_record(tmp_path: Path) -> None:
    """Load a single valid adversarial record from JSONL."""
    dataset_path = tmp_path / "test_adv.jsonl"
    record = {
        "id": "a-001",
        "subject": "Test subject",
        "body": "Test body content",
        "attack_category": "direct_injection",
        "expected_behavior": "Should block",
        "notes": "Test note",
    }
    dataset_path.write_text(json.dumps(record) + "\n")

    result = load_adversarial_dataset(dataset_path)

    assert len(result) == 1
    assert result[0].id == "a-001"
    assert result[0].subject == "Test subject"
    assert result[0].body == "Test body content"
    assert result[0].attack_category == "direct_injection"
    assert result[0].expected_behavior == "Should block"
    assert result[0].notes == "Test note"


def test_load_adversarial_dataset_multiple_records(tmp_path: Path) -> None:
    """Load multiple adversarial records from JSONL."""
    dataset_path = tmp_path / "test_adv.jsonl"
    records = [
        {
            "id": "a-001",
            "subject": "First",
            "body": "First body",
            "attack_category": "direct_injection",
            "expected_behavior": "Block",
            "notes": "Note 1",
        },
        {
            "id": "a-002",
            "subject": "Second",
            "body": "Second body",
            "attack_category": "indirect_injection_quoted",
            "expected_behavior": "Ignore",
            "notes": "Note 2",
        },
    ]
    dataset_path.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    result = load_adversarial_dataset(dataset_path)

    assert len(result) == 2
    assert result[0].id == "a-001"
    assert result[0].attack_category == "direct_injection"
    assert result[1].id == "a-002"
    assert result[1].attack_category == "indirect_injection_quoted"


def test_load_adversarial_dataset_skips_blank_lines(tmp_path: Path) -> None:
    """Skip blank lines in JSONL."""
    dataset_path = tmp_path / "test_adv.jsonl"
    record = {
        "id": "a-001",
        "subject": "Test",
        "body": "Body",
        "attack_category": "direct_injection",
        "expected_behavior": "Block",
        "notes": "Note",
    }
    content = "\n" + json.dumps(record) + "\n\n"
    dataset_path.write_text(content)

    result = load_adversarial_dataset(dataset_path)

    assert len(result) == 1
    assert result[0].id == "a-001"


def test_load_adversarial_dataset_missing_file(tmp_path: Path) -> None:
    """Raise FileNotFoundError when dataset file doesn't exist."""
    dataset_path = tmp_path / "nonexistent.jsonl"

    with pytest.raises(FileNotFoundError, match="Dataset not found"):
        load_adversarial_dataset(dataset_path)


def test_load_real_adversarial_dataset() -> None:
    """Load the real adversarial dataset if present (skip if not)."""
    dataset_path = Path("data/adversarial_set.jsonl")
    if not dataset_path.exists():
        pytest.skip("Real adversarial dataset not present")

    result = load_adversarial_dataset(dataset_path)

    assert len(result) > 0
    # Check first record has expected fields
    assert result[0].id
    assert result[0].subject
    assert result[0].body
    assert result[0].attack_category
    assert result[0].expected_behavior
    assert result[0].notes


def test_adversarial_to_ticket_record_produces_correct_structure() -> None:
    """Adapter produces a TicketRecord with dummy ground truth."""
    adv_record = AdversarialTicketRecord(
        id="a-001",
        subject="Test subject",
        body="Test body",
        attack_category="direct_injection",
        expected_behavior="Block",
        notes="Test note",
    )

    result = adversarial_to_ticket_record(adv_record)

    assert isinstance(result, TicketRecord)
    assert result.id == "a-001"
    assert result.subject == "Test subject"
    assert result.body == "Test body"
    assert isinstance(result.ground_truth, GroundTruth)
    assert result.ground_truth.category == "other"
    assert result.ground_truth.severity == "medium"
    assert result.ground_truth.routing_team == "support"
    assert result.ground_truth.escalation is False


def test_adversarial_to_ticket_record_preserves_all_fields() -> None:
    """Adapter preserves id, subject, and body exactly."""
    adv_record = AdversarialTicketRecord(
        id="special-id-123",
        subject="Exact subject text",
        body="Exact body text with\nmultiple lines",
        attack_category="pii_data_leak",
        expected_behavior="Warn",
        notes="Multi-line\nnotes",
    )

    result = adversarial_to_ticket_record(adv_record)

    assert result.id == "special-id-123"
    assert result.subject == "Exact subject text"
    assert result.body == "Exact body text with\nmultiple lines"
