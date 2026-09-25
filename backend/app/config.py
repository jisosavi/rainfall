from datetime import date
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="postgresql+psycopg://user:password@localhost:5432/rainfall", alias="DATABASE_URL")
    port: int = Field(default=8000, alias="PORT")
    # Comma-separated string, e.g. "https://isosavi.com,https://www.isosavi.com".
    # Kept as str because pydantic-settings expects JSON for list fields.
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")
    # First date loaded when the database is empty.
    ingest_start_date: date = Field(default=date(2025, 1, 1), alias="INGEST_START_DATE")
    # Recent days re-fetched on every run, since FMI revises recent values.
    ingest_refetch_days: int = Field(default=10, alias="INGEST_REFETCH_DAYS")

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Railway provides postgresql:// (or postgres://), which SQLAlchemy maps to psycopg2.
        # We ship psycopg 3, so force its driver name.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
