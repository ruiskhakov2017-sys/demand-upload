"""add persisted product workflow

Revision ID: 202607210002
Revises: 202607190001
Create Date: 2026-07-21
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202607210002"
down_revision = "202607190001"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "campaign_uploads",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_rows", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("draft", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_campaign_uploads_status"), "campaign_uploads", ["status"], unique=False)
    op.create_index(op.f("ix_campaign_uploads_connection_id"), "campaign_uploads", ["connection_id"], unique=False)
    op.create_index(op.f("ix_campaign_uploads_created_by_id"), "campaign_uploads", ["created_by_id"], unique=False)

    op.create_table(
        "media_assets",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("aspect_ratio", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("youtube_video_id", sa.String(length=32), nullable=True),
        sa.Column("youtube_upload_resource", sa.String(length=255), nullable=True),
        sa.Column("google_asset_resources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "sha256", name="uq_media_kind_sha256"),
    )
    op.create_index(op.f("ix_media_assets_kind"), "media_assets", ["kind"], unique=False)
    op.create_index(op.f("ix_media_assets_sha256"), "media_assets", ["sha256"], unique=False)
    op.create_index(op.f("ix_media_assets_status"), "media_assets", ["status"], unique=False)
    op.create_index(op.f("ix_media_assets_youtube_video_id"), "media_assets", ["youtube_video_id"], unique=False)
    op.create_index(op.f("ix_media_assets_created_by_id"), "media_assets", ["created_by_id"], unique=False)

    op.create_table(
        "campaign_templates",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_campaign_templates_is_active"), "campaign_templates", ["is_active"], unique=False)
    op.create_index(op.f("ix_campaign_templates_created_by_id"), "campaign_templates", ["created_by_id"], unique=False)

    op.create_table(
        "oauth_authorizations",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=512), nullable=False),
        sa.Column("code_verifier_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_oauth_authorizations_state_hash"), "oauth_authorizations", ["state_hash"], unique=True)
    op.create_index(
        op.f("ix_oauth_authorizations_connection_id"),
        "oauth_authorizations",
        ["connection_id"],
        unique=False,
    )
    op.create_index(op.f("ix_oauth_authorizations_expires_at"), "oauth_authorizations", ["expires_at"], unique=False)
    op.create_index(
        op.f("ix_oauth_authorizations_created_by_id"),
        "oauth_authorizations",
        ["created_by_id"],
        unique=False,
    )

    op.create_table(
        "deployment_plans",
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("execution_mode", sa.String(length=20), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("local_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("google_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resource_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["upload_id"], ["campaign_uploads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deployment_plans_upload_id"), "deployment_plans", ["upload_id"], unique=False)
    op.create_index(op.f("ix_deployment_plans_connection_id"), "deployment_plans", ["connection_id"], unique=False)
    op.create_index(op.f("ix_deployment_plans_status"), "deployment_plans", ["status"], unique=False)
    op.create_index(op.f("ix_deployment_plans_execution_mode"), "deployment_plans", ["execution_mode"], unique=False)
    op.create_index(op.f("ix_deployment_plans_fingerprint"), "deployment_plans", ["fingerprint"], unique=True)
    op.create_index(op.f("ix_deployment_plans_created_by_id"), "deployment_plans", ["created_by_id"], unique=False)

    op.create_table(
        "moderation_records",
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("resource_name", sa.String(length=255), nullable=False),
        sa.Column("approval_status", sa.String(length=40), nullable=False),
        sa.Column("policy_topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["plan_id"], ["deployment_plans.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "resource_name", name="uq_moderation_customer_resource"),
    )
    op.create_index(op.f("ix_moderation_records_connection_id"), "moderation_records", ["connection_id"], unique=False)
    op.create_index(op.f("ix_moderation_records_customer_id"), "moderation_records", ["customer_id"], unique=False)
    op.create_index(
        op.f("ix_moderation_records_approval_status"),
        "moderation_records",
        ["approval_status"],
        unique=False,
    )

    op.create_table(
        "metric_snapshots",
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("snapshot_date", sa.String(length=10), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_metric_snapshots_connection_id"), "metric_snapshots", ["connection_id"], unique=False)
    op.create_index(op.f("ix_metric_snapshots_customer_id"), "metric_snapshots", ["customer_id"], unique=False)
    op.create_index(op.f("ix_metric_snapshots_snapshot_date"), "metric_snapshots", ["snapshot_date"], unique=False)

    op.create_table(
        "finance_profiles",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["credential_id"], ["google_credentials.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_finance_profiles_status"), "finance_profiles", ["status"], unique=False)
    op.create_index(op.f("ix_finance_profiles_created_by_id"), "finance_profiles", ["created_by_id"], unique=False)

    op.create_table(
        "finance_snapshots",
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("cards_total", sa.Integer(), nullable=False),
        sa.Column("cards_active", sa.Integer(), nullable=False),
        sa.Column("provider_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["profile_id"], ["finance_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_finance_snapshots_profile_id"), "finance_snapshots", ["profile_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_index(op.f("ix_notifications_severity"), "notifications", ["severity"], unique=False)


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("finance_snapshots")
    op.drop_table("finance_profiles")
    op.drop_table("metric_snapshots")
    op.drop_table("moderation_records")
    op.drop_table("deployment_plans")
    op.drop_table("oauth_authorizations")
    op.drop_table("campaign_templates")
    op.drop_table("media_assets")
    op.drop_table("campaign_uploads")
