import json
from pathlib import Path

import pytest

from ticket_triage_llm.eval.datasets import GroundTruth, TicketRecord, load_dataset


class TestLoadDataset:
    def test_loads_valid_jsonl(self, tmp_path):
        jsonl = tmp_path / "test.jsonl"
        jsonl.write_text(
            json.dumps({
                "id": "n-001",
                "subject": "Billing issue",
                "body": "I have a billing question",
                "ground_truth": {
                    "category": "billing",
                    "severity": "medium",
                    "routing_team": "billing",
                    "escalation": False,
                },
            })
            + "\n"
        )
        tickets = load_dataset(jsonl)
        assert len(tickets) == 1
        assert tickets[0].id == "n-001"
        assert tickets[0].subject == "Billing issue"
        assert tickets[0].body == "I have a billing question"
        assert tickets[0].ground_truth.category == "billing"
        assert tickets[0].ground_truth.severity == "medium"
        assert tickets[0].ground_truth.routing_team == "billing"
        assert tickets[0].ground_truth.escalation is False

    def test_loads_multiple_lines(self, tmp_path):
        jsonl = tmp_path / "multi.jsonl"
        lines = []
        for i in range(3):
            lines.append(
                json.dumps({
                    "id": f"n-{i:03d}",
                    "subject": f"Subject {i}",
                    "body": f"Body {i}",
                    "ground_truth": {
                        "category": "billing",
                        "severity": "low",
                        "routing_team": "support",
                        "escalation": False,
                    },
                })
            )
        jsonl.write_text("\n".join(lines) + "\n")
        tickets = load_dataset(jsonl)
        assert len(tickets) == 3
        assert tickets[2].id == "n-002"

    def test_skips_blank_lines(self, tmp_path):
        jsonl = tmp_path / "blanks.jsonl"
        line = json.dumps({
            "id": "n-001",
            "subject": "S",
            "body": "B",
            "ground_truth": {
                "category": "billing",
                "severity": "low",
                "routing_team": "support",
                "escalation": False,
            },
        })
        jsonl.write_text(line + "\n\n\n")
        tickets = load_dataset(jsonl)
        assert len(tickets) == 1

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_dataset(Path("/nonexistent/file.jsonl"))
