"""Application settings loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the ticket-triage-llm application.

    All fields can be overridden via environment variables (upper-cased).
    Sampling parameters are locked per the 2026-04-16 decision-log entry:
    temperature 0.2, top_p 0.9, top_k 40, repetition_penalty 1.0.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str
    temperature: float = 0.2
    top_p: float = 0.9
    top_k: int = 40
    repetition_penalty: float = 1.0
    db_path: str = "data/traces.db"
    log_level: str = "INFO"
