"""campaign builder and test bundles

Revision ID: 202607220003
Revises: 202607210002
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607220003"
down_revision: str | None = "202607210002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.add_column("campaign_templates", sa.Column("semantic_key", sa.String(length=160), nullable=True))
    op.add_column(
        "campaign_templates",
        sa.Column("current_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_index(op.f("ix_campaign_templates_semantic_key"), "campaign_templates", ["semantic_key"])

    op.create_table(
        "campaign_template_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("source_campaign_resource", sa.String(length=255), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["template_id"], ["campaign_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_id", "version_number", name="uq_template_version"),
    )
    op.create_index(op.f("ix_campaign_template_versions_template_id"), "campaign_template_versions", ["template_id"])
    op.create_index(
        op.f("ix_campaign_template_versions_created_by_id"), "campaign_template_versions", ["created_by_id"]
    )
    op.execute(
        """
        INSERT INTO campaign_template_versions
            (id, template_id, version_number, payload, change_summary, created_by_id, created_at, updated_at)
        SELECT gen_random_uuid(), id, 1, payload, 'Initial version migrated from template',
               created_by_id, created_at, updated_at
        FROM campaign_templates
        """
    )

    op.create_table(
        "launch_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("connection_id", sa.Uuid(), nullable=True),
        sa.Column("template_version_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("creation_mode", sa.String(length=40), nullable=False),
        sa.Column("execution_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("generation_seed", sa.String(length=160), nullable=False),
        sa.Column("generation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name_pattern", sa.String(length=512), nullable=False),
        sa.Column("builder_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("financial_preview", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["upload_id"], ["campaign_uploads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connection_id"], ["google_connections.id"]),
        sa.ForeignKeyConstraint(["template_version_id"], ["campaign_template_versions.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("upload_id", "connection_id", "template_version_id", "execution_mode", "status", "created_by_id"):
        op.create_index(op.f(f"ix_launch_batches_{column}"), "launch_batches", [column])

    op.create_table(
        "account_test_bundles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("launch_batch_id", sa.Uuid(), nullable=False),
        sa.Column("customer_account_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("currency_code", sa.String(length=16), nullable=False),
        sa.Column("time_zone", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("campaigns_count", sa.Integer(), nullable=False),
        sa.Column("override_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("winner_instance_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["launch_batch_id"], ["launch_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_account_id"], ["customer_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("launch_batch_id", "customer_id", name="uq_batch_customer_bundle"),
    )
    for column in ("launch_batch_id", "customer_account_id", "customer_id", "status", "winner_instance_id"):
        op.create_index(op.f(f"ix_account_test_bundles_{column}"), "account_test_bundles", [column])

    op.create_table(
        "budget_generation_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("launch_batch_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("distribution", sa.String(length=40), nullable=False),
        sa.Column("fixed_micros", sa.BigInteger(), nullable=True),
        sa.Column("minimum_micros", sa.BigInteger(), nullable=True),
        sa.Column("maximum_micros", sa.BigInteger(), nullable=True),
        sa.Column("step_micros", sa.BigInteger(), nullable=False),
        sa.Column("decimal_places", sa.Integer(), nullable=False),
        sa.Column("allow_repeats", sa.Boolean(), nullable=False),
        sa.Column("seed", sa.String(length=160), nullable=False),
        sa.Column("manual_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("per_currency", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["launch_batch_id"], ["launch_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("launch_batch_id"),
    )
    op.create_index(
        op.f("ix_budget_generation_configs_launch_batch_id"),
        "budget_generation_configs",
        ["launch_batch_id"],
        unique=True,
    )

    op.create_table(
        "campaign_instances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("launch_batch_id", sa.Uuid(), nullable=False),
        sa.Column("account_test_bundle_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_plan_id", sa.Uuid(), nullable=True),
        sa.Column("template_version_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("campaign_sequence", sa.Integer(), nullable=False),
        sa.Column("campaign_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("policy_status", sa.String(length=40), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("budget_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency_code", sa.String(length=16), nullable=False),
        sa.Column("budget_mode", sa.String(length=40), nullable=False),
        sa.Column("generation_seed", sa.String(length=160), nullable=False),
        sa.Column("copy_mode", sa.String(length=40), nullable=False),
        sa.Column("deployment_key", sa.String(length=64), nullable=False),
        sa.Column("campaign_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bidding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("targeting", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("url_settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("texts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("creative_assignment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("override_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("local_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("google_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resource_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["launch_batch_id"], ["launch_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_test_bundle_id"], ["account_test_bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deployment_plan_id"], ["deployment_plans.id"]),
        sa.ForeignKeyConstraint(["template_version_id"], ["campaign_template_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_test_bundle_id", "campaign_sequence", name="uq_bundle_campaign_sequence"),
        sa.UniqueConstraint("launch_batch_id", "campaign_name", name="uq_batch_campaign_name"),
        sa.UniqueConstraint("deployment_key", name="uq_campaign_instance_deployment_key"),
    )
    for column in (
        "launch_batch_id",
        "account_test_bundle_id",
        "deployment_plan_id",
        "customer_id",
        "status",
        "policy_status",
        "deployment_key",
    ):
        op.create_index(op.f(f"ix_campaign_instances_{column}"), "campaign_instances", [column])

    op.create_table(
        "campaign_instance_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("launch_batch_id", sa.Uuid(), nullable=False),
        sa.Column("account_test_bundle_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_instance_id", sa.Uuid(), nullable=True),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["launch_batch_id"], ["launch_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_test_bundle_id"], ["account_test_bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_instance_id"], ["campaign_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("launch_batch_id", "account_test_bundle_id", "campaign_instance_id", "created_by_id"):
        op.create_index(op.f(f"ix_campaign_instance_overrides_{column}"), "campaign_instance_overrides", [column])

    op.create_table(
        "creative_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_instance_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=True),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("google_resource_name", sa.String(length=255), nullable=True),
        sa.Column("assignment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["campaign_instance_id"], ["campaign_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_asset_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("campaign_instance_id", "media_asset_id", "customer_id", "sha256"):
        op.create_index(op.f(f"ix_creative_assignments_{column}"), "creative_assignments", [column])

    op.create_table(
        "performance_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_instance_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("account_time_zone", sa.String(length=80), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=False),
        sa.Column("clicks", sa.BigInteger(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("conversions", sa.Float(), nullable=False),
        sa.Column("conversion_value", sa.Float(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["campaign_instance_id"], ["campaign_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_performance_snapshots_campaign_instance_id"),
        "performance_snapshots",
        ["campaign_instance_id"],
    )
    op.create_index(op.f("ix_performance_snapshots_period_start"), "performance_snapshots", ["period_start"])
    op.create_index(op.f("ix_performance_snapshots_period_end"), "performance_snapshots", ["period_end"])

    op.create_table(
        "evaluation_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("launch_batch_id", sa.Uuid(), nullable=True),
        sa.Column("account_test_bundle_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("rule_type", sa.String(length=80), nullable=False),
        sa.Column("action_mode", sa.String(length=40), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["launch_batch_id"], ["launch_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_test_bundle_id"], ["account_test_bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("launch_batch_id", "account_test_bundle_id", "is_active", "created_by_id"):
        op.create_index(op.f(f"ix_evaluation_rules_{column}"), "evaluation_rules", [column])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_test_bundle_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_rule_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommendation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics_at_run", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("executed_action", sa.Boolean(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["account_test_bundle_id"], ["account_test_bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evaluation_rule_id"], ["evaluation_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evaluation_runs_account_test_bundle_id"), "evaluation_runs", ["account_test_bundle_id"])
    op.create_index(op.f("ix_evaluation_runs_evaluation_rule_id"), "evaluation_runs", ["evaluation_rule_id"])

    op.create_table(
        "winner_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_test_bundle_id", sa.Uuid(), nullable=False),
        sa.Column("winner_instance_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("paused_instance_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_by_id", sa.Uuid(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["account_test_bundle_id"], ["account_test_bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["winner_instance_id"], ["campaign_instances.id"]),
        sa.ForeignKeyConstraint(["decided_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("account_test_bundle_id", "winner_instance_id", "decided_by_id", "decided_at"):
        op.create_index(op.f(f"ix_winner_decisions_{column}"), "winner_decisions", [column])

    op.create_table(
        "campaign_status_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_test_bundle_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_instance_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("previous_status", sa.String(length=40), nullable=True),
        sa.Column("requested_status", sa.String(length=40), nullable=False),
        sa.Column("execution_mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("selected_instance_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("request_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("resource_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["account_test_bundle_id"], ["account_test_bundles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_instance_id"], ["campaign_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("account_test_bundle_id", "campaign_instance_id", "status", "requested_by_id"):
        op.create_index(op.f(f"ix_campaign_status_actions_{column}"), "campaign_status_actions", [column])

    op.create_table(
        "application_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index(op.f("ix_application_settings_key"), "application_settings", ["key"], unique=True)

    op.add_column("deployment_plans", sa.Column("launch_batch_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_deployment_plans_launch_batch_id",
        "deployment_plans",
        "launch_batches",
        ["launch_batch_id"],
        ["id"],
    )
    op.create_index(op.f("ix_deployment_plans_launch_batch_id"), "deployment_plans", ["launch_batch_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_deployment_plans_launch_batch_id"), table_name="deployment_plans")
    op.drop_constraint("fk_deployment_plans_launch_batch_id", "deployment_plans", type_="foreignkey")
    op.drop_column("deployment_plans", "launch_batch_id")
    for table in (
        "application_settings",
        "campaign_status_actions",
        "winner_decisions",
        "evaluation_runs",
        "evaluation_rules",
        "performance_snapshots",
        "creative_assignments",
        "campaign_instance_overrides",
        "campaign_instances",
        "budget_generation_configs",
        "account_test_bundles",
        "launch_batches",
        "campaign_template_versions",
    ):
        op.drop_table(table)
    op.drop_index(op.f("ix_campaign_templates_semantic_key"), table_name="campaign_templates")
    op.drop_column("campaign_templates", "current_version")
    op.drop_column("campaign_templates", "semantic_key")
