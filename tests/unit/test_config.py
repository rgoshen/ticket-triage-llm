import pytest
from pydantic import ValidationError

from ticket_triage_llm.config import Settings


class TestSettingsDefaults:
    def test_ollama_base_url_default(self):
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.ollama_base_url == "http://localhost:11434/v1"

    def test_locked_sampling_defaults(self):
        """Sampling params are locked per 2026-04-16 decision-log entry."""
        settings = Settings(ollama_model="qwen3.5:4b")
        assert settings.temperature == 0.2
        assert settings.top_p == 0.9
        assert settings.top_k == 40
        assert settings.repetition_penalty == 1.0

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

    def test_temperature_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("TEMPERATURE", "0.5")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.temperature == 0.5

    def test_db_path_override(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "qwen3.5:4b")
        monkeypatch.setenv("DB_PATH", "/tmp/custom.db")
        settings = Settings()  # type: ignore[call-arg]
        assert settings.db_path == "/tmp/custom.db"


class TestSettingsRequired:
    def test_missing_model_raises(self, monkeypatch):
        """OLLAMA_MODEL has no default -- must be set explicitly."""
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)
