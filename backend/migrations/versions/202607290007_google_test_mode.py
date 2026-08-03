"""add isolated google test execution mode

Revision ID: 202607290007
Revises: fabc2ba828ea
Create Date: 2026-07-29 13:30:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "202607290007"
down_revision = "fabc2ba828ea"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "google_connections",
        sa.Column(
            "connection_mode",
            sa.String(length=24),
            server_default=sa.text("'PRODUCTION'"),
            nullable=False,
        ),
    )
    op.add_column(
        "google_connections",
        sa.Column("oauth_client_credential_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "google_connections",
        sa.Column("oauth_refresh_credential_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "google_connections",
        sa.Column("test_hierarchy_root_customer_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "google_connections",
        sa.Column("hierarchy_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "google_connections",
        sa.Column(
            "hierarchy_request_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_google_connections_oauth_client_credential",
        "google_connections",
        "google_credentials",
        ["oauth_client_credential_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_google_connections_oauth_refresh_credential",
        "google_connections",
        "google_credentials",
        ["oauth_refresh_credential_id"],
        ["id"],
    )
    op.create_index(
        "ix_google_connections_connection_mode",
        "google_connections",
        ["connection_mode"],
        unique=False,
    )
    op.create_index(
        "ix_google_connections_test_hierarchy_root_customer_id",
        "google_connections",
        ["test_hierarchy_root_customer_id"],
        unique=False,
    )
    op.execute(
        """
        UPDATE google_connections
        SET oauth_client_credential_id = auth_credential_id
        WHERE auth_type = 'OAUTH_WEB'
          AND auth_credential_id IS NOT NULL
          AND oauth_client_credential_id IS NULL
        """
    )

    op.add_column(
        "mcc_accounts",
        sa.Column(
            "is_test_account",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column("mcc_accounts", sa.Column("status", sa.String(length=40), nullable=True))
    op.add_column(
        "mcc_accounts",
        sa.Column(
            "request_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "mcc_accounts",
        sa.Column("last_sync_success_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "customer_accounts",
        sa.Column("hierarchy_root_customer_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "customer_accounts",
        sa.Column(
            "account_type",
            sa.String(length=24),
            server_default=sa.text("'CLIENT'"),
            nullable=False,
        ),
    )
    op.add_column(
        "customer_accounts",
        sa.Column("test_account_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "customer_accounts",
        sa.Column(
            "last_google_request_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_customer_accounts_hierarchy_root_customer_id",
        "customer_accounts",
        ["hierarchy_root_customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_customer_accounts_account_type",
        "customer_accounts",
        ["account_type"],
        unique=False,
    )
    op.create_index(
        "ix_customer_accounts_test_account_verified_at",
        "customer_accounts",
        ["test_account_verified_at"],
        unique=False,
    )

    op.add_column(
        "account_monitoring_states",
        sa.Column(
            "data_source_mode",
            sa.String(length=24),
            server_default=sa.text("'UNKNOWN'"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_account_monitoring_states_data_source_mode",
        "account_monitoring_states",
        ["data_source_mode"],
        unique=False,
    )
    op.add_column(
        "account_metric_daily",
        sa.Column(
            "data_source_mode",
            sa.String(length=24),
            server_default=sa.text("'UNKNOWN'"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_account_metric_daily_data_source_mode",
        "account_metric_daily",
        ["data_source_mode"],
        unique=False,
    )

    op.create_table(
        "google_test_acceptance_runs",
        sa.Column("connection_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("fixture_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=True),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column(
            "resource_names",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "request_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "readback",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["deployment_plans.id"]),
        sa.ForeignKeyConstraint(["upload_id"], ["campaign_uploads.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "connection_id",
            "customer_id",
            "purpose",
            name="uq_google_test_acceptance_run",
        ),
    )
    op.create_index(
        "ix_google_test_acceptance_runs_connection_id",
        "google_test_acceptance_runs",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        "ix_google_test_acceptance_runs_customer_id",
        "google_test_acceptance_runs",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_google_test_acceptance_runs_fixture_name",
        "google_test_acceptance_runs",
        ["fixture_name"],
        unique=False,
    )
    op.create_index(
        "ix_google_test_acceptance_runs_purpose",
        "google_test_acceptance_runs",
        ["purpose"],
        unique=False,
    )
    op.create_index(
        "ix_google_test_acceptance_runs_status",
        "google_test_acceptance_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_google_test_acceptance_runs_status",
        table_name="google_test_acceptance_runs",
    )
    op.drop_index(
        "ix_google_test_acceptance_runs_purpose",
        table_name="google_test_acceptance_runs",
    )
    op.drop_index(
        "ix_google_test_acceptance_runs_fixture_name",
        table_name="google_test_acceptance_runs",
    )
    op.drop_index(
        "ix_google_test_acceptance_runs_customer_id",
        table_name="google_test_acceptance_runs",
    )
    op.drop_index(
        "ix_google_test_acceptance_runs_connection_id",
        table_name="google_test_acceptance_runs",
    )
    op.drop_table("google_test_acceptance_runs")

    op.drop_index(
        "ix_account_metric_daily_data_source_mode",
        table_name="account_metric_daily",
    )
    op.drop_column("account_metric_daily", "data_source_mode")
    op.drop_index(
        "ix_account_monitoring_states_data_source_mode",
        table_name="account_monitoring_states",
    )
    op.drop_column("account_monitoring_states", "data_source_mode")

    op.drop_index(
        "ix_customer_accounts_test_account_verified_at",
        table_name="customer_accounts",
    )
    op.drop_index(
        "ix_customer_accounts_account_type",
        table_name="customer_accounts",
    )
    op.drop_index(
        "ix_customer_accounts_hierarchy_root_customer_id",
        table_name="customer_accounts",
    )
    op.drop_column("customer_accounts", "last_google_request_ids")
    op.drop_column("customer_accounts", "test_account_verified_at")
    op.drop_column("customer_accounts", "account_type")
    op.drop_column("customer_accounts", "hierarchy_root_customer_id")

    op.drop_column("mcc_accounts", "last_sync_success_at")
    op.drop_column("mcc_accounts", "request_ids")
    op.drop_column("mcc_accounts", "status")
    op.drop_column("mcc_accounts", "is_test_account")

    op.drop_index(
        "ix_google_connections_test_hierarchy_root_customer_id",
        table_name="google_connections",
    )
    op.drop_index(
        "ix_google_connections_connection_mode",
        table_name="google_connections",
    )
    op.drop_constraint(
        "fk_google_connections_oauth_refresh_credential",
        "google_connections",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_google_connections_oauth_client_credential",
        "google_connections",
        type_="foreignkey",
    )
    op.drop_column("google_connections", "hierarchy_request_ids")
    op.drop_column("google_connections", "hierarchy_verified_at")
    op.drop_column("google_connections", "test_hierarchy_root_customer_id")
    op.drop_column("google_connections", "oauth_refresh_credential_id")
    op.drop_column("google_connections", "oauth_client_credential_id")
    op.drop_column("google_connections", "connection_mode")
