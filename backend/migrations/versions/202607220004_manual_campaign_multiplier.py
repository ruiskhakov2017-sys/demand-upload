"""remove automatic campaign evaluation

Revision ID: 202607220004
Revises: 202607220003
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607220004"
down_revision: str | None = "202607220003"
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
    op.drop_table("winner_decisions")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_rules")
    op.drop_index(
        op.f("ix_account_test_bundles_winner_instance_id"),
        table_name="account_test_bundles",
    )
    op.drop_column("account_test_bundles", "winner_instance_id")


def downgrade() -> None:
    op.add_column(
        "account_test_bundles",
        sa.Column("winner_instance_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        op.f("ix_account_test_bundles_winner_instance_id"),
        "account_test_bundles",
        ["winner_instance_id"],
    )
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
        sa.ForeignKeyConstraint(
            ["account_test_bundle_id"],
            ["account_test_bundles.id"],
            ondelete="CASCADE",
        ),
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
        sa.ForeignKeyConstraint(
            ["account_test_bundle_id"],
            ["account_test_bundles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["evaluation_rule_id"], ["evaluation_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_runs_account_test_bundle_id"),
        "evaluation_runs",
        ["account_test_bundle_id"],
    )
    op.create_index(
        op.f("ix_evaluation_runs_evaluation_rule_id"),
        "evaluation_runs",
        ["evaluation_rule_id"],
    )

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
        sa.ForeignKeyConstraint(
            ["account_test_bundle_id"],
            ["account_test_bundles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["winner_instance_id"], ["campaign_instances.id"]),
        sa.ForeignKeyConstraint(["decided_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("account_test_bundle_id", "winner_instance_id", "decided_by_id", "decided_at"):
        op.create_index(op.f(f"ix_winner_decisions_{column}"), "winner_decisions", [column])
