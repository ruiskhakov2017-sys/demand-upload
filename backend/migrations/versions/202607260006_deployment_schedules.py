"""add deferred deployment schedules

Revision ID: 202607260006
Revises: 202607220005
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607260006"
down_revision: str | None = "202607220005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "deployment_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deployment_plan_id", sa.Uuid(), nullable=True),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("launch_batch_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("parent_schedule_id", sa.Uuid(), nullable=True),
        sa.Column("mcc_customer_id", sa.String(length=32), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("time_zone", sa.String(length=80), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_accounts_per_hour", sa.Integer(), nullable=False),
        sa.Column("max_accounts_per_day", sa.Integer(), nullable=False),
        sa.Column("max_parallel", sa.Integer(), nullable=False),
        sa.Column("circuit_breaker_threshold", sa.Integer(), nullable=False),
        sa.Column("consecutive_serious_errors", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("manual_approval", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pause_reason", sa.Text(), nullable=True),
        sa.Column("recovery_required", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_dispatch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["deployment_plan_id"], ["deployment_plans.id"]),
        sa.ForeignKeyConstraint(["upload_id"], ["campaign_uploads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.ForeignKeyConstraint(["launch_batch_id"], ["launch_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["parent_schedule_id"], ["deployment_schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint"),
        sa.UniqueConstraint("launch_batch_id", "version_number", name="uq_schedule_batch_version"),
    )
    for column in (
        "deployment_plan_id",
        "upload_id",
        "connection_id",
        "launch_batch_id",
        "job_id",
        "parent_schedule_id",
        "mcc_customer_id",
        "mode",
        "status",
        "start_at",
        "fingerprint",
        "is_current",
        "created_by_id",
    ):
        op.create_index(op.f(f"ix_deployment_schedules_{column}"), "deployment_schedules", [column])
    op.create_index("ix_schedule_batch_current", "deployment_schedules", ["launch_batch_id", "is_current"])

    op.create_table(
        "deployment_waves",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("wave_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["schedule_id"], ["deployment_schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "wave_number", name="uq_schedule_wave_number"),
    )
    for column in ("schedule_id", "status", "starts_at"):
        op.create_index(op.f(f"ix_deployment_waves_{column}"), "deployment_waves", [column])

    op.create_table(
        "scheduled_account_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("wave_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_plan_id", sa.Uuid(), nullable=True),
        sa.Column("account_test_bundle_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("campaigns_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deployment_key", sa.String(length=64), nullable=False),
        sa.Column("resource_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("structured_error", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["schedule_id"], ["deployment_schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wave_id"], ["deployment_waves.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deployment_plan_id"], ["deployment_plans.id"]),
        sa.ForeignKeyConstraint(["account_test_bundle_id"], ["account_test_bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "account_test_bundle_id", name="uq_schedule_bundle_run"),
    )
    for column in (
        "schedule_id",
        "wave_id",
        "deployment_plan_id",
        "account_test_bundle_id",
        "customer_id",
        "scheduled_for",
        "status",
        "next_retry_at",
        "deployment_key",
        "created_by_id",
    ):
        op.create_index(op.f(f"ix_scheduled_account_runs_{column}"), "scheduled_account_runs", [column])
    op.create_index(
        "ix_scheduled_runs_due",
        "scheduled_account_runs",
        ["status", "scheduled_for", "next_retry_at"],
    )

    op.create_table(
        "schedule_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("wave_id", sa.Uuid(), nullable=True),
        sa.Column("account_run_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["schedule_id"], ["deployment_schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wave_id"], ["deployment_waves.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_run_id"], ["scheduled_account_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("schedule_id", "wave_id", "account_run_id", "actor_user_id", "event_type"):
        op.create_index(op.f(f"ix_schedule_events_{column}"), "schedule_events", [column])


def downgrade() -> None:
    op.drop_table("schedule_events")
    op.drop_table("scheduled_account_runs")
    op.drop_table("deployment_waves")
    op.drop_table("deployment_schedules")
