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
    # Days re-loaded from SMHI's corrected archive by --archive-refresh (latest-months spans ~4 months).
    smhi_archive_refresh_days: int = Field(default=130, alias="SMHI_ARCHIVE_REFRESH_DAYS")
    # MET Norway Frost API client ID (https://frost.met.no). Optional; MET is skipped without it.
    frost_client_id: str | None = Field(default=None, alias="FROST_CLIENT_ID")
    # The address agents are told to use (MCP at <this>/mcp); change it when a custom domain is added.
    public_base_url: str = Field(default="https://rainfall-production.up.railway.app", alias="PUBLIC_BASE_URL")
    # Traffic limits (app.limits). MCP tool calls per session, per IP (higher for the trusted
    # ranges: Anthropic's outbound addresses, shared by all Claude users) and globally; above the
    # global rate the tools pause for MCP_PAUSE_MINUTES. REST: per IP. 0 turns a REST limit off.
    mcp_session_per_minute: int = Field(default=60, alias="MCP_SESSION_PER_MINUTE")
    mcp_session_per_day: int = Field(default=1500, alias="MCP_SESSION_PER_DAY")
    mcp_ip_per_minute: int = Field(default=60, alias="MCP_IP_PER_MINUTE")
    mcp_trusted_ip_per_minute: int = Field(default=1000, alias="MCP_TRUSTED_IP_PER_MINUTE")
    mcp_trusted_ranges_raw: str = Field(default="160.79.104.0/21", alias="MCP_TRUSTED_IP_RANGES")
    mcp_global_per_minute: int = Field(default=1200, alias="MCP_GLOBAL_PER_MINUTE")
    mcp_pause_minutes: int = Field(default=15, alias="MCP_PAUSE_MINUTES")
    rest_ip_per_minute: int = Field(default=300, alias="REST_IP_PER_MINUTE")
    # Web requests' database statements are cancelled after this long (ingestion isn't limited).
    statement_timeout_ms: int = Field(default=10000, alias="STATEMENT_TIMEOUT_MS")

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
    def mcp_trusted_ranges(self) -> tuple[str, ...]:
        return tuple(r.strip() for r in self.mcp_trusted_ranges_raw.split(",") if r.strip())

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
