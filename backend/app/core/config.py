"""Load and validate application settings from the environment."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    """Application configuration loaded from environment variables / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    APP_ENV: Literal["development", "production"] = "development"
    DEBUG: bool | None = None

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str

    # LLM (Phase 5)
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    LLM_TIMEOUT_SECONDS: int = 30

    # Web security and logging
    CORS_ALLOWED_ORIGINS: str | None = None
    TRUSTED_HOSTS: str | None = None
    LOG_LEVEL: str = "INFO"

    @property
    def debug_enabled(self) -> bool:
        return self.DEBUG if self.DEBUG is not None else self.APP_ENV == "development"

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ALLOWED_ORIGINS:
            return [
                origin.strip()
                for origin in self.CORS_ALLOWED_ORIGINS.split(",")
                if origin.strip()
            ]
        if self.APP_ENV == "development":
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return []

    @property
    def trusted_hosts(self) -> list[str]:
        if self.TRUSTED_HOSTS:
            return [
                host.strip()
                for host in self.TRUSTED_HOSTS.split(",")
                if host.strip()
            ]
        if self.APP_ENV == "development":
            return ["localhost", "127.0.0.1", "testserver"]
        return []

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if self.LOG_LEVEL.upper() not in {
            "CRITICAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
        }:
            raise RuntimeError("LOG_LEVEL must be a standard Python logging level")

        if self.APP_ENV != "production":
            return self

        if self.debug_enabled:
            raise RuntimeError("DEBUG must be false in production")
        if len(self.SECRET_KEY) < 32 or self._looks_like_placeholder(self.SECRET_KEY):
            raise RuntimeError("SECRET_KEY must be a non-placeholder value of at least 32 characters")
        if not self.GEMINI_API_KEY or self._looks_like_placeholder(self.GEMINI_API_KEY):
            raise RuntimeError("GEMINI_API_KEY must be configured in production")
        if "DATABASE_URL" not in self.model_fields_set:
            raise RuntimeError("DATABASE_URL must be explicitly configured in production")

        try:
            database_url = make_url(self.DATABASE_URL)
        except ArgumentError as exc:
            raise RuntimeError("DATABASE_URL is invalid") from exc
        if database_url.get_backend_name() != "postgresql" or not database_url.host:
            raise RuntimeError("DATABASE_URL must point to a PostgreSQL server in production")
        if database_url.host in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("DATABASE_URL must use an external PostgreSQL host in production")

        if not self.cors_origins or not all(
            self._is_production_origin(origin) for origin in self.cors_origins
        ):
            raise RuntimeError("CORS_ALLOWED_ORIGINS must contain explicit HTTPS origins in production")
        if not self.trusted_hosts or any("*" in host for host in self.trusted_hosts):
            raise RuntimeError("TRUSTED_HOSTS must contain explicit hosts in production")
        return self

    @staticmethod
    def _is_production_origin(origin: str) -> bool:
        try:
            parsed = urlsplit(origin)
            return (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
                and parsed.username is None
                and parsed.password is None
            )
        except ValueError:
            return False

    @staticmethod
    def _looks_like_placeholder(value: str) -> bool:
        lowered = value.lower()
        return any(
            marker in lowered
            for marker in ("replace-with", "change-me", "your-api-key", "placeholder")
        )


settings = Settings()
