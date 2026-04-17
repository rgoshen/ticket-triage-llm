import pytest
from pydantic import ValidationError

from ticket_triage_llm.config import (
    REPETITION_PENALTY,
    TEMPERATURE,
    TOP_K,
    TOP_P,
    Settings,
)


class TestLockedSamplingConstants:
    """Sampling params are module-level constants, not configurable fields.

    Changing any value requires a decision-log entry (2026-04-16 lock).
    """

    def test_temperature(self):
        assert TEMPERATURE == 0.2

    def test_top_p(self):
        assert TOP_P == 0.9

    def test_top_k(self):
        assert TOP_K == 40

    def test_repetition_penalty(self):
        assert REPETITION_PENALTY == 1.0

    def test_not_on_settings(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert not hasattr(settings, "temperature")
        assert not hasattr(settings, "top_p")
        assert not hasattr(settings, "top_k")
        assert not hasattr(settings, "repetition_penalty")


class TestSettingsDefaults:
    def test_ollama_base_url_default(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.ollama_base_url == "http://localhost:11434/v1"

    def test_db_path_default(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.db_path == "data/traces.db"

    def test_log_level_default(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.log_level == "INFO"


class TestSettingsEnvOverrides:
    def test_ollama_base_url_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://remote:11434/v1")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:9b")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.ollama_base_url == "http://remote:11434/v1"

    def test_ollama_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:9b")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.ollama_model == "qwen3.5:9b"

    def test_db_path_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.db_path == "/tmp/custom.db"

    def test_sampling_env_vars_ignored(self, monkeypatch):
        """Env vars for sampling params must not leak into Settings."""
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("TEMPERATURE", "0.9")
        settings = Settings()  # type: ignore[call-arg]
        assert not hasattr(settings, "temperature")


class TestSettingsRequired:
    def test_missing_model_raises(self, monkeypatch):
        """OLLAMA_MODEL has no default -- must be set explicitly."""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


class TestOllamaModelsConfig:
    def test_ollama_models_parsed_from_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("OLLAMA_MODELS", "qwen3.5:2b,qwen3.5:4b,qwen3.5:9b")
        settings = Settings(_env_file=None)
        assert settings.ollama_models == "qwen3.5:2b,qwen3.5:4b,qwen3.5:9b"

    def test_guardrail_max_length_default(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("OLLAMA_MODELS", "qwen3.5:4b")
        settings = Settings(_env_file=None)
        assert settings.guardrail_max_length == 10_000
