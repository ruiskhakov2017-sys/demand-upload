from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Axyro Analytics"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_public_base_url: str = Field(default="http://localhost", alias="APP_PUBLIC_BASE_URL")
    api_prefix: str = "/api"
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )
    allowed_hosts: list[str] = Field(default_factory=lambda: ["*"], alias="ALLOWED_HOSTS")
    session_cookie_name: str = "dgu_session"
    session_cookie_secure: bool = Field(default=True, alias="SESSION_COOKIE_SECURE")
    session_ttl_minutes: int = 720
    setup_token: str | None = Field(default=None, alias="SETUP_TOKEN")
    app_encryption_key: str = Field(alias="APP_ENCRYPTION_KEY")
    google_ads_api_version: str = Field(default="v24.2", alias="GOOGLE_ADS_API_VERSION")
    control_center_live_actions_enabled: bool = Field(
        default=False, alias="CONTROL_CENTER_LIVE_ACTIONS_ENABLED"
    )
    control_center_daily_operation_limit: int = Field(
        default=15_000, ge=100, alias="CONTROL_CENTER_DAILY_OPERATION_LIMIT"
    )
    storage_root: Path = Field(default=Path("/var/lib/dgu/storage"), alias="STORAGE_ROOT")
    domain_validation_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    domain_validation_max_redirects: int = Field(default=5, ge=1, le=10)
    domain_validation_max_parallel: int = Field(default=6, ge=1, le=20)
    domain_validation_cache_minutes: int = Field(default=360, ge=1, le=1440)
    web_risk_enabled: bool = Field(default=False, alias="WEB_RISK_ENABLED")
    web_risk_api_key: str | None = Field(default=None, alias="WEB_RISK_API_KEY")
    spamhaus_dqs_enabled: bool = Field(default=False, alias="SPAMHAUS_DQS_ENABLED")
    spamhaus_dqs_key: str | None = Field(default=None, alias="SPAMHAUS_DQS_KEY")
    ipqs_enabled: bool = Field(default=False, alias="IPQS_ENABLED")
    ipqs_api_key: str | None = Field(default=None, alias="IPQS_API_KEY")
    domain_reputation_enforcement: str = Field(default="monitor", alias="DOMAIN_REPUTATION_ENFORCEMENT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def parse_string_list(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("domain_reputation_enforcement")
    @classmethod
    def validate_reputation_enforcement(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"monitor", "block"}:
            raise ValueError("DOMAIN_REPUTATION_ENFORCEMENT must be monitor or block")
        return normalized

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
