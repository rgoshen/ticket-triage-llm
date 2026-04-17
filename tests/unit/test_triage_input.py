import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.triage_input import TriageInput


class TestTriageInput:
    def test_valid_minimal(self):
        ti = TriageInput(ticket_body="My account is locked")
        assert ti.ticket_body == "My account is locked"
        assert ti.ticket_subject == ""
        assert ti.model is None
        assert ti.prompt_version == "v1"

    def test_valid_all_fields(self):
        ti = TriageInput(
            ticket_body="My account is locked",
            ticket_subject="Account Issue",
            model="qwen3.5:4b",
            prompt_version="v2",
        )
        assert ti.ticket_subject == "Account Issue"
        assert ti.model == "qwen3.5:4b"
        assert ti.prompt_version == "v2"

    def test_empty_body_rejected(self):
        with pytest.raises(ValidationError):
            TriageInput(ticket_body="")

    def test_whitespace_only_body_rejected(self):
        with pytest.raises(ValidationError):
            TriageInput(ticket_body="   \n\t  ")

    def test_missing_body_rejected(self):
        with pytest.raises(ValidationError):
            TriageInput()  # type: ignore[call-arg]

    def test_round_trip_json(self):
        ti = TriageInput(ticket_body="test", ticket_subject="subj")
        data = ti.model_dump()
        restored = TriageInput.model_validate(data)
        assert restored == ti
