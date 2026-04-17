import pytest
from pydantic import ValidationError

from ticket_triage_llm.schemas.model_result import ModelResult


class TestModelResult:
    def test_valid_construction(self):
        mr = ModelResult(
            raw_output='{"category": "billing"}',
            model="qwen3.5:4b",
            latency_ms=1234.5,
            tokens_input=150,
            tokens_output=200,
            tokens_total=350,
        )
        assert mr.raw_output == '{"category": "billing"}'
        assert mr.model == "qwen3.5:4b"
        assert mr.tokens_total == 350

    def test_optional_tokens_per_second(self):
        mr = ModelResult(
            raw_output="{}",
            model="qwen3.5:2b",
            latency_ms=100.0,
            tokens_input=10,
            tokens_output=20,
            tokens_total=30,
            tokens_per_second=36.5,
        )
        assert mr.tokens_per_second == 36.5

    def test_tokens_per_second_defaults_none(self):
        mr = ModelResult(
            raw_output="{}",
            model="qwen3.5:2b",
            latency_ms=100.0,
            tokens_input=10,
            tokens_output=20,
            tokens_total=30,
        )
        assert mr.tokens_per_second is None

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            ModelResult(
                raw_output="{}",
                latency_ms=100.0,
                tokens_input=10,
                tokens_output=20,
                tokens_total=30,
            )  # type: ignore[call-arg]

    def test_round_trip(self):
        mr = ModelResult(
            raw_output="test",
            model="qwen3.5:9b",
            latency_ms=500.0,
            tokens_input=100,
            tokens_output=200,
            tokens_total=300,
        )
        restored = ModelResult.model_validate(mr.model_dump())
        assert restored == mr
