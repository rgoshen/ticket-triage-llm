"""Application settings loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict

TEMPERATURE: float = 0.2
TOP_P: float = 0.9
TOP_K: int = 40
REPETITION_PENALTY: float = 1.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str
    ollama_models: str = ""
    guardrail_max_length: int = 10_000
    db_path: str = "data/traces.db"
    log_level: str = "INFO"
