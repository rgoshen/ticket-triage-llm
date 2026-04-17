import pytest

from ticket_triage_llm.services.prompt import get_prompt


class TestGetPrompt:
    def test_v1_returns_tuple_of_two_strings(self):
        system, user = get_prompt("v1", "Test Subject", "My printer is broken")
        assert isinstance(system, str)
        assert isinstance(user, str)

    def test_v1_system_prompt_contains_json_schema(self):
        system, _ = get_prompt("v1", "", "test")
        assert '"category"' in system
        assert '"severity"' in system
        assert '"routingTeam"' in system

    def test_v1_user_prompt_contains_ticket_body(self):
        _, user = get_prompt("v1", "Subject", "My printer broke yesterday")
        assert "My printer broke yesterday" in user

    def test_v1_user_prompt_contains_subject(self):
        _, user = get_prompt("v1", "Printer Issue", "body text")
        assert "Printer Issue" in user

    def test_v1_user_prompt_has_ticket_delimiters(self):
        _, user = get_prompt("v1", "Subject", "body text")
        assert "<ticket>" in user
        assert "</ticket>" in user

    def test_unknown_version_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown prompt version"):
            get_prompt("v99", "Subject", "body")

    def test_repair_version_passes_through_args(self):
        system, user = get_prompt("__repair__", "system text", "user text")
        assert system == "system text"
        assert user == "user text"
