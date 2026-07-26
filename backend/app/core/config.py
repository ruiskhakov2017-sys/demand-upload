from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Demand Gen Uploader"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_public_base_url: str = Field(default="http://localhost", alias="APP_PUBLIC_BASE_URL")
    api_prefix: str = "/api"
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost", "http://localhost:5173"],
        alias="CORS_ORIGINS",
    )
    session_cookie_name: str = "dgu_session"
    session_cookie_secure: bool = Field(default=True, alias="SESSION_COOKIE_SECURE")
    session_ttl_minutes: int = 720
    setup_token: str | None = Field(default=None, alias="SETUP_TOKEN")
    app_encryption_key: str = Field(alias="APP_ENCRYPTION_KEY")
    google_ads_api_version: str = Field(default="v24.2", alias="GOOGLE_ADS_API_VERSION")
    storage_root: Path = Field(default=Path("/var/lib/dgu/storage"), alias="STORAGE_ROOT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
