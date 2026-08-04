from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Axyro Analytics"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_public_base_url: str = Field(default="http://localhost", alias="APP_PUBLIC_BASE_URL")
    app_version_sha: str = Field(default="development", alias="APP_VERSION_SHA")
    app_release_tag: str | None = Field(default=None, alias="APP_RELEASE_TAG")
    app_deployed_at: str | None = Field(default=None, alias="APP_DEPLOYED_AT")
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
    control_center_live_actions_enabled: bool = Field(default=False, alias="CONTROL_CENTER_LIVE_ACTIONS_ENABLED")
    control_center_daily_operation_limit: int = Field(
        default=15_000, ge=100, alias="CONTROL_CENTER_DAILY_OPERATION_LIMIT"
    )
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    ai_enabled: bool = Field(default=True, alias="AI_ENABLED")
    ai_kill_switch: bool = Field(default=False, alias="AI_KILL_SWITCH")
    ai_production_read_enabled: bool = Field(default=False, alias="AI_PRODUCTION_READ_ENABLED")
    ai_production_actions_enabled: bool = Field(default=False, alias="AI_PRODUCTION_ACTIONS_ENABLED")
    ai_pause_actions_enabled: bool = Field(default=False, alias="AI_PAUSE_ACTIONS_ENABLED")
    ai_enable_actions_enabled: bool = Field(default=False, alias="AI_ENABLE_ACTIONS_ENABLED")
    ai_budget_actions_enabled: bool = Field(default=False, alias="AI_BUDGET_ACTIONS_ENABLED")
    ai_demand_gen_actions_enabled: bool = Field(default=False, alias="AI_DEMAND_GEN_ACTIONS_ENABLED")
    ai_live_rules_enabled: bool = Field(default=False, alias="AI_LIVE_RULES_ENABLED")
    ai_max_model_turns: int = Field(default=4, ge=1, le=8, alias="AI_MAX_MODEL_TURNS")
    ai_max_read_tool_calls: int = Field(default=6, ge=1, le=20, alias="AI_MAX_READ_TOOL_CALLS")
    ai_max_draft_tool_calls: int = Field(default=1, ge=0, le=3, alias="AI_MAX_DRAFT_TOOL_CALLS")
    ai_max_rows_per_tool: int = Field(default=100, ge=1, le=500, alias="AI_MAX_ROWS_PER_TOOL")
    ai_max_date_range_days: int = Field(default=90, ge=1, le=730, alias="AI_MAX_DATE_RANGE_DAYS")
    ai_interactive_timeout_seconds: int = Field(default=60, ge=10, le=180, alias="AI_INTERACTIVE_TIMEOUT_SECONDS")
    ai_retention_days: int = Field(default=30, ge=1, le=365, alias="AI_RETENTION_DAYS")
    ai_rate_limit_per_minute: int = Field(default=10, ge=1, le=120, alias="AI_RATE_LIMIT_PER_MINUTE")
    ai_global_rate_limit_per_minute: int = Field(
        default=60, ge=1, le=1000, alias="AI_GLOBAL_RATE_LIMIT_PER_MINUTE"
    )
    ai_max_concurrent_runs: int = Field(default=2, ge=1, le=10, alias="AI_MAX_CONCURRENT_RUNS")
    ai_global_max_concurrent_runs: int = Field(default=8, ge=1, le=100, alias="AI_GLOBAL_MAX_CONCURRENT_RUNS")
    ai_daily_soft_budget_usd: float = Field(default=5.0, ge=0, alias="AI_DAILY_SOFT_BUDGET_USD")
    ai_daily_hard_budget_usd: float = Field(default=10.0, ge=0, alias="AI_DAILY_HARD_BUDGET_USD")
    ai_monthly_hard_budget_usd: float = Field(default=100.0, ge=0, alias="AI_MONTHLY_HARD_BUDGET_USD")
    ai_user_daily_hard_budget_usd: float = Field(default=5.0, ge=0, alias="AI_USER_DAILY_HARD_BUDGET_USD")
    ai_user_monthly_hard_budget_usd: float = Field(default=50.0, ge=0, alias="AI_USER_MONTHLY_HARD_BUDGET_USD")
    ai_provider_circuit_failure_threshold: int = Field(
        default=3, ge=1, le=20, alias="AI_PROVIDER_CIRCUIT_FAILURE_THRESHOLD"
    )
    ai_provider_circuit_cooldown_seconds: int = Field(
        default=300, ge=30, le=3600, alias="AI_PROVIDER_CIRCUIT_COOLDOWN_SECONDS"
    )
    ai_voice_max_seconds: int = Field(default=60, ge=1, le=300, alias="AI_VOICE_MAX_SECONDS")
    ai_voice_max_bytes: int = Field(default=10_485_760, ge=1024, le=52_428_800, alias="AI_VOICE_MAX_BYTES")
    ai_transcription_model: str = Field(default="gpt-4o-mini-transcribe", alias="AI_TRANSCRIPTION_MODEL")
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
