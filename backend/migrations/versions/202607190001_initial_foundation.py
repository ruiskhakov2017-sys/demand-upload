"""initial production foundation

Revision ID: 202607190001
Revises:
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202607190001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_setup_admin", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "google_credentials",
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("encrypted_payload", sa.LargeBinary(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("last_rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_google_credentials_kind"), "google_credentials", ["kind"], unique=False)

    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=160), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_sessions_expires_at"), "user_sessions", ["expires_at"], unique=False)
    op.create_index(op.f("ix_user_sessions_token_hash"), "user_sessions", ["token_hash"], unique=True)

    op.create_table(
        "google_connections",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("login_customer_id", sa.String(length=32), nullable=False),
        sa.Column("auth_type", sa.String(length=40), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("developer_token_credential_id", sa.Uuid(), nullable=True),
        sa.Column("auth_credential_id", sa.Uuid(), nullable=True),
        sa.Column("api_version", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["auth_credential_id"], ["google_credentials.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["developer_token_credential_id"], ["google_credentials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_google_connections_auth_type"), "google_connections", ["auth_type"], unique=False)
    op.create_index(
        op.f("ix_google_connections_login_customer_id"),
        "google_connections",
        ["login_customer_id"],
        unique=False,
    )

    op.create_table(
        "mcc_accounts",
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("descriptive_name", sa.String(length=255), nullable=True),
        sa.Column("currency_code", sa.String(length=16), nullable=True),
        sa.Column("time_zone", sa.String(length=80), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "customer_id", name="uq_mcc_connection_customer"),
    )
    op.create_index(op.f("ix_mcc_accounts_connection_id"), "mcc_accounts", ["connection_id"], unique=False)
    op.create_index(op.f("ix_mcc_accounts_customer_id"), "mcc_accounts", ["customer_id"], unique=False)

    op.create_table(
        "customer_accounts",
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("manager_customer_id", sa.String(length=32), nullable=True),
        sa.Column("descriptive_name", sa.String(length=255), nullable=True),
        sa.Column("currency_code", sa.String(length=16), nullable=True),
        sa.Column("time_zone", sa.String(length=80), nullable=True),
        sa.Column("can_manage_clients", sa.Boolean(), nullable=False),
        sa.Column("is_test_account", sa.Boolean(), nullable=False),
        sa.Column("is_hidden", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", "customer_id", name="uq_customer_connection_customer"),
    )
    op.create_index(op.f("ix_customer_accounts_connection_id"), "customer_accounts", ["connection_id"], unique=False)
    op.create_index(op.f("ix_customer_accounts_customer_id"), "customer_accounts", ["customer_id"], unique=False)
    op.create_index(
        op.f("ix_customer_accounts_manager_customer_id"),
        "customer_accounts",
        ["manager_customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_accounts_connection_manager",
        "customer_accounts",
        ["connection_id", "manager_customer_id"],
        unique=False,
    )

    op.create_table(
        "jobs",
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=180), nullable=True),
        sa.Column("progress_current", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_idempotency_key"), "jobs", ["idempotency_key"], unique=True)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)
    op.create_index(op.f("ix_jobs_type"), "jobs", ["type"], unique=False)

    op.create_table(
        "job_events",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_events_job_id"), "job_events", ["job_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=True),
        sa.Column("entity_id", sa.String(length=80), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("job_events")
    op.drop_table("jobs")
    op.drop_index("ix_customer_accounts_connection_manager", table_name="customer_accounts")
    op.drop_table("customer_accounts")
    op.drop_table("mcc_accounts")
    op.drop_table("google_connections")
    op.drop_table("user_sessions")
    op.drop_table("google_credentials")
    op.drop_table("users")
