"""
config.py — Application settings loaded from .env via Pydantic BaseSettings.
All downstream modules import `settings` directly; never read os.environ manually.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jlpt_trainer"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:70b"

    # Piper TTS
    piper_binary: str = "piper"
    piper_model_path: str = "static/piper/ja_JP-kokoro-medium.onnx"

    # SRS defaults
    new_cards_per_day: int = 20

    # App
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Module-level singleton used by routers and core modules
settings: Settings = get_settings()
