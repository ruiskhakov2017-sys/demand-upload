"""add AI analyst, GEO analytics profiles and final account workflow fields

Revision ID: 202608030011
Revises: 202607300010
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202608030011"
down_revision: str | None = "202607300010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.add_column("customer_accounts", sa.Column("pinned_note", sa.Text(), nullable=True))
    op.add_column("customer_accounts", sa.Column("pinned_note_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_accounts", sa.Column("pinned_note_updated_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_customer_accounts_pinned_note_updated_by",
        "customer_accounts",
        "users",
        ["pinned_note_updated_by_id"],
        ["id"],
    )
    op.add_column(
        "account_note_history",
        sa.Column("note_kind", sa.String(length=20), server_default="REGULAR", nullable=False),
    )
    op.create_index(op.f("ix_account_note_history_note_kind"), "account_note_history", ["note_kind"], unique=False)
    op.execute("UPDATE customer_accounts SET work_status = 'PREPARATION' WHERE work_status = 'UNCLASSIFIED'")
    op.execute("UPDATE customer_accounts SET work_status = 'MANUAL_PAUSE' WHERE work_status = 'PAUSED'")

    op.create_table(
        "account_work_status_history",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=30), server_default="LOCAL", nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["customer_accounts.id"]),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("account_id", "status", "source", "changed_at"):
        op.create_index(op.f(f"ix_account_work_status_history_{column}"), "account_work_status_history", [column])

    op.create_table(
        "ai_conversations",
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), server_default="Новый диалог", nullable=False),
        sa.Column("authority_mode", sa.String(length=30), server_default="READ_ONLY", nullable=False),
        sa.Column("google_environment", sa.String(length=24), server_default="SIMULATION", nullable=False),
        sa.Column("scope", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("locale", sa.String(length=12), server_default="ru", nullable=False),
        sa.Column("time_zone", sa.String(length=80), server_default="Europe/Moscow", nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "owner_user_id",
        "authority_mode",
        "google_environment",
        "last_message_at",
        "archived_at",
        "deleted_at",
        "retention_until",
    ):
        op.create_index(op.f(f"ix_ai_conversations_{column}"), "ai_conversations", [column])

    op.create_table(
        "ai_runs",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="QUEUED", nullable=False),
        sa.Column("model_profile", sa.String(length=24), server_default="BALANCED", nullable=False),
        sa.Column("model_id", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=40), server_default="ai-analyst-v1", nullable=False),
        sa.Column("tool_schema_version", sa.String(length=40), server_default="axyro-tools-v1", nullable=False),
        sa.Column("authority_mode", sa.String(length=30), nullable=False),
        sa.Column("google_environment", sa.String(length=24), nullable=False),
        sa.Column("resolved_scope", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(14, 8), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("model_turns", sa.Integer(), server_default="0", nullable=False),
        sa.Column("read_tool_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("draft_tool_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("partial", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    for column in (
        "conversation_id",
        "user_id",
        "request_id",
        "status",
        "model_profile",
        "model_id",
        "authority_mode",
        "google_environment",
        "cancel_requested",
        "error_code",
    ):
        op.create_index(op.f(f"ix_ai_runs_{column}"), "ai_runs", [column], unique=column == "request_id")

    op.create_table(
        "ai_messages",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_content", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("evidence", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="COMPLETE", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("conversation_id", "user_id", "run_id", "role", "status"):
        op.create_index(op.f(f"ix_ai_messages_{column}"), "ai_messages", [column])

    op.create_table(
        "ai_tool_calls",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("tool_call_id", sa.String(length=180), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("tool_version", sa.String(length=40), nullable=False),
        sa.Column("risk_class", sa.String(length=30), nullable=False),
        sa.Column("arguments", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="RUNNING", nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("call_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "call_fingerprint", name="uq_ai_tool_call_fingerprint"),
    )
    for column in ("run_id", "tool_call_id", "tool_name", "risk_class", "status", "call_fingerprint"):
        op.create_index(op.f(f"ix_ai_tool_calls_{column}"), "ai_tool_calls", [column])

    op.create_table(
        "ai_drafts",
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("draft_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="EDITABLE", nullable=False),
        sa.Column("authority_mode", sa.String(length=30), nullable=False),
        sa.Column("google_environment", sa.String(length=24), nullable=False),
        sa.Column("scope", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_snapshot", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_entity_type", sa.String(length=80), nullable=True),
        sa.Column("linked_entity_id", sa.String(length=80), nullable=True),
        sa.Column("action_request_id", sa.Uuid(), nullable=True),
        sa.Column("deployment_plan_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["action_request_id"], ["control_center_action_requests.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deployment_plan_id"], ["deployment_plans.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "owner_user_id",
        "conversation_id",
        "draft_type",
        "status",
        "fingerprint",
        "expires_at",
        "action_request_id",
        "deployment_plan_id",
    ):
        op.create_index(op.f(f"ix_ai_drafts_{column}"), "ai_drafts", [column])

    op.create_table(
        "ai_saved_reports",
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("report", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("scope", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("owner_user_id", "conversation_id", "expires_at"):
        op.create_index(op.f(f"ix_ai_saved_reports_{column}"), "ai_saved_reports", [column])

    op.create_table(
        "ai_usage_daily",
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.String(length=80), nullable=False),
        sa.Column("requests", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(14, 8), server_default="0", nullable=False),
        sa.Column("tool_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("errors", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms_total", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usage_date", "user_id", "model_id", name="uq_ai_usage_daily_user_model"),
    )
    for column in ("usage_date", "user_id", "model_id"):
        op.create_index(op.f(f"ix_ai_usage_daily_{column}"), "ai_usage_daily", [column])

    op.create_table(
        "ai_user_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("default_authority_mode", sa.String(length=30), server_default="READ_ONLY", nullable=False),
        sa.Column("default_environment", sa.String(length=24), server_default="SIMULATION", nullable=False),
        sa.Column("default_model_profile", sa.String(length=24), server_default="BALANCED", nullable=False),
        sa.Column("default_scope", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("locale", sa.String(length=12), server_default="ru", nullable=False),
        sa.Column("time_zone", sa.String(length=80), server_default="Europe/Moscow", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_ai_user_preferences_user_id"), "ai_user_preferences", ["user_id"], unique=True)

    op.create_table(
        "ai_admin_settings",
        sa.Column("key", sa.String(length=80), server_default="global", nullable=False),
        sa.Column("settings", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("openai_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("openai_key_last_four", sa.String(length=4), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_ai_admin_settings_key"), "ai_admin_settings", ["key"], unique=True)

    op.create_table(
        "ai_model_profiles",
        sa.Column("name", sa.String(length=24), nullable=False),
        sa.Column("model_id", sa.String(length=80), nullable=False),
        sa.Column("reasoning_effort", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("verbosity", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="60", nullable=False),
        sa.Column("max_input_tokens", sa.Integer(), server_default="32000", nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), server_default="4000", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("price_metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("eval_version", sa.String(length=80), nullable=True),
        sa.Column("eval_passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_ai_model_profiles_name"), "ai_model_profiles", ["name"], unique=True)
    op.create_index(op.f("ix_ai_model_profiles_model_id"), "ai_model_profiles", ["model_id"])
    op.create_index(op.f("ix_ai_model_profiles_enabled"), "ai_model_profiles", ["enabled"])
    model_profiles = sa.table(
        "ai_model_profiles",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("model_id", sa.String()),
        sa.column("reasoning_effort", sa.String()),
        sa.column("verbosity", sa.String()),
        sa.column("timeout_seconds", sa.Integer()),
        sa.column("max_input_tokens", sa.Integer()),
        sa.column("max_output_tokens", sa.Integer()),
        sa.column("enabled", sa.Boolean()),
        sa.column("price_metadata", JSONB),
    )
    op.bulk_insert(
        model_profiles,
        [
            {
                "id": "20000000-0000-4000-8000-000000000001",
                "name": "FAST",
                "model_id": "gpt-5.6-luna",
                "reasoning_effort": "low",
                "verbosity": "low",
                "timeout_seconds": 45,
                "max_input_tokens": 24000,
                "max_output_tokens": 3000,
                "enabled": True,
                "price_metadata": {
                    "currency": "USD",
                    "unit": "1M_TOKENS",
                    "input": 1.0,
                    "cached_input": 0.1,
                    "output": 6.0,
                    "verified_on": "2026-08-03",
                },
            },
            {
                "id": "20000000-0000-4000-8000-000000000002",
                "name": "BALANCED",
                "model_id": "gpt-5.6-terra",
                "reasoning_effort": "medium",
                "verbosity": "medium",
                "timeout_seconds": 60,
                "max_input_tokens": 32000,
                "max_output_tokens": 4000,
                "enabled": True,
                "price_metadata": {
                    "currency": "USD",
                    "unit": "1M_TOKENS",
                    "input": 2.5,
                    "cached_input": 0.25,
                    "output": 15.0,
                    "verified_on": "2026-08-03",
                },
            },
            {
                "id": "20000000-0000-4000-8000-000000000003",
                "name": "DEEP",
                "model_id": "gpt-5.6-sol",
                "reasoning_effort": "high",
                "verbosity": "high",
                "timeout_seconds": 60,
                "max_input_tokens": 48000,
                "max_output_tokens": 6000,
                "enabled": True,
                "price_metadata": {
                    "currency": "USD",
                    "unit": "1M_TOKENS",
                    "input": 5.0,
                    "cached_input": 0.5,
                    "output": 30.0,
                    "verified_on": "2026-08-03",
                },
            },
        ],
    )

    op.create_table(
        "geo_analytics_profiles",
        sa.Column("scope_type", sa.String(length=24), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("geo_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_zone", sa.String(length=80), server_default="UTC", nullable=False),
        sa.Column("expected_currencies", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("default_reporting_period", sa.String(length=30), server_default="7d", nullable=False),
        sa.Column("primary_metric_source", sa.String(length=40), server_default="GOOGLE_ADS", nullable=False),
        sa.Column("target_cpl", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_registration_cpa", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_deposit_cpa", sa.Numeric(18, 6), nullable=True),
        sa.Column("target_roas", sa.Numeric(18, 6), nullable=True),
        sa.Column("max_spend_without_lead", sa.Numeric(18, 6), nullable=True),
        sa.Column("max_spend_without_registration", sa.Numeric(18, 6), nullable=True),
        sa.Column("max_spend_without_deposit", sa.Numeric(18, 6), nullable=True),
        sa.Column("minimum_clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minimum_impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("minimum_spend", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("conversion_lag_hours", sa.Integer(), server_default="24", nullable=False),
        sa.Column("alert_thresholds", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("owner_comment", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["geo_id"], ["geo_definitions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_type", "scope_id", "version", name="uq_geo_analytics_profile_scope_version"),
    )
    for column in ("scope_type", "scope_id", "geo_id", "is_active", "created_by_id"):
        op.create_index(op.f(f"ix_geo_analytics_profiles_{column}"), "geo_analytics_profiles", [column])

    op.create_table(
        "geo_analytics_profile_history",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["profile_id"], ["geo_analytics_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("profile_id", "version", "changed_at"):
        op.create_index(op.f(f"ix_geo_analytics_profile_history_{column}"), "geo_analytics_profile_history", [column])

    op.create_table(
        "geo_analytics_overrides",
        sa.Column("scope_type", sa.String(length=24), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("override_values", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["profile_id"], ["geo_analytics_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_type", "scope_id", name="uq_geo_analytics_override_scope"),
    )
    for column in ("scope_type", "scope_id", "profile_id", "is_active", "updated_by_id"):
        op.create_index(op.f(f"ix_geo_analytics_overrides_{column}"), "geo_analytics_overrides", [column])

    op.create_table(
        "metric_source_mappings",
        sa.Column("scope_type", sa.String(length=24), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=True),
        sa.Column("semantic_metric", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("attribution_model", sa.String(length=80), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("metadata_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_type",
            "scope_id",
            "semantic_metric",
            "provider",
            "source_id",
            name="uq_metric_source_mapping",
        ),
    )
    for column in ("scope_type", "scope_id", "semantic_metric", "provider", "is_active", "created_by_id"):
        op.create_index(op.f(f"ix_metric_source_mappings_{column}"), "metric_source_mappings", [column])


def downgrade() -> None:
    raise RuntimeError(
        "Migration 202608030011 is intentionally additive and cannot be downgraded without deleting AI history."
    )
