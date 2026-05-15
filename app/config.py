import logging
import os
from functools import lru_cache
from json import loads
from pathlib import Path
from typing import Any

from pydantic import EmailStr, Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("app.config")
ENV_FILE_PATH = Path(".env")
REQUIRED_ENV_VARS = ("DATABASE_URL", "JWT_SECRET_KEY", "JWT_REFRESH_SECRET_KEY")


class Settings(BaseSettings):
    app_name: str = "MF_MANAGER"
    app_env: str = "development"
    debug: bool = False

    api_prefix: str = "/api"
    api_v1_prefix: str = "/api/v1"
    app_port: int = Field(default=8010, validation_alias="APP_PORT")
    database_url: str = Field(validation_alias="DATABASE_URL")
    sql_echo: bool = False

    jwt_secret_key: str = Field(min_length=32, validation_alias="JWT_SECRET_KEY")
    jwt_refresh_secret_key: str = Field(min_length=32, validation_alias="JWT_REFRESH_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    first_admin_email: EmailStr | None = None
    first_admin_password: str | None = Field(default=None, min_length=8, max_length=128)

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        enable_decoding=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        raise TypeError("cors_origins must be a list, JSON array, or comma-separated string")

    @field_validator("first_admin_email", "first_admin_password", mode="before")
    @classmethod
    def empty_string_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_secrets_and_first_admin(self) -> "Settings":
        if self.jwt_secret_key == self.jwt_refresh_secret_key:
            raise ValueError("JWT_SECRET_KEY and JWT_REFRESH_SECRET_KEY must be different")
        if bool(self.first_admin_email) != bool(self.first_admin_password):
            raise ValueError("FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD must be set together")
        return self


def _config_source_label() -> str:
    return f".env ({ENV_FILE_PATH.resolve()})" if ENV_FILE_PATH.exists() else "environment variables"


def _assert_required_configuration_present() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing and not ENV_FILE_PATH.exists():
        missing_list = ", ".join(missing)
        raise RuntimeError(
            "Configuration error: .env file not found and required environment variables are missing. "
            f"Expected {_config_source_label()} with values for: {missing_list}"
        )


def log_startup_configuration(settings: Settings) -> None:
    logger.info(
        "configuration_loaded",
        extra={
            "config_source": _config_source_label(),
            "app_env": settings.app_env,
            "app_port": settings.app_port,
            "database_url_present": bool(settings.database_url),
            "jwt_secret_key_present": bool(settings.jwt_secret_key),
            "jwt_refresh_secret_key_present": bool(settings.jwt_refresh_secret_key),
        },
    )


@lru_cache
def get_settings() -> Settings:
    _assert_required_configuration_present()
    try:
        settings = Settings()
    except ValidationError as exc:
        raise RuntimeError(
            f"Configuration error while loading settings from {_config_source_label()}: {exc}"
        ) from exc
    return settings
