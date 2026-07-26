"""add server defaults to campaign builder timestamps

Revision ID: 202607220005
Revises: 202607220004
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607220005"
down_revision: str | None = "202607220004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "campaign_template_versions",
    "launch_batches",
    "account_test_bundles",
    "budget_generation_configs",
    "campaign_instances",
    "campaign_instance_overrides",
    "creative_assignments",
    "performance_snapshots",
    "campaign_status_actions",
    "application_settings",
)


def upgrade() -> None:
    for table in TABLES:
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            existing_nullable=False,
        )
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=None,
            existing_nullable=False,
        )
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=None,
            existing_nullable=False,
        )
