"""Typed application settings, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_ENV: Literal["dev", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    API_TOKEN: str = Field(..., min_length=8, description="Static bearer token for v1 single-user mode")

    # --- DB ---
    DATABASE_URL: str = Field(..., description="postgresql+asyncpg://...")

    # --- Storage ---
    STORAGE_BACKEND: Literal["local", "minio", "s3"] = "local"
    STORAGE_ROOT: str = "./data"

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173"

    @field_validator("DATABASE_URL")
    @classmethod
    def _ensure_async_driver(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
