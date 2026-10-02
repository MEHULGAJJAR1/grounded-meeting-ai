"""Typed, environment-driven configuration. No credentials live in source."""

from functools import lru_cache
from pathlib import Path
from typing import Literal
import secrets

from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", extra="ignore", case_sensitive=False, hide_input_in_errors=True
    )
    app_env: Literal["development", "production", "test"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    ai_provider: Literal["auto", "openai", "local"] = "auto"
    openai_timeout_seconds: int = Field(default=90, ge=10, le=300)
    database_url: str = "sqlite:///./data/grounded.db"
    jwt_secret_key: str = ""
    access_token_expire_minutes: int = Field(default=120, ge=5, le=1440)
    upload_dir: str = "./uploads"
    max_upload_size: int = Field(default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    max_transcript_chars: int = Field(default=150000, ge=100, le=500000)
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    allow_demo_data: bool = True
    log_level: str = "INFO"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    @model_validator(mode="after")
    def validate_secrets(self):
        if self.app_env == "production":
            if len(self.jwt_secret_key) < 32:
                raise ValueError("Production requires JWT_SECRET_KEY of at least 32 characters")
            if self.allow_demo_data:
                raise ValueError("Set ALLOW_DEMO_DATA=false in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
        if not self.jwt_secret_key:
            # In a bare development run this is ephemeral; the one-command runner
            # writes a persistent, randomly generated secret to the ignored .env.
            self.jwt_secret_key = secrets.token_urlsafe(48)
        if self.ai_provider == "openai" and not self.openai_api_key:
            raise ValueError("AI_PROVIDER=openai requires OPENAI_API_KEY")
        return self

    @property
    def active_provider(self) -> str:
        return "openai" if self.ai_provider != "local" and self.openai_api_key else "local"

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        return path if path.is_absolute() else ROOT / path

    @property
    def origins(self) -> list[str]:
        return [value.strip() for value in self.cors_origins.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
