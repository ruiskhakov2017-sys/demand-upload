"""Add optional second approval to Control Center actions.

Revision ID: 202608040012
Revises: 202608030011
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608040012"
down_revision: str | None = "202608030011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "control_center_action_requests",
        sa.Column("second_approval_required", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "control_center_action_requests",
        sa.Column("second_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "control_center_action_requests",
        sa.Column("second_approved_by_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_control_center_action_second_approved_by",
        "control_center_action_requests",
        "users",
        ["second_approved_by_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_control_center_action_second_approved_by",
        "control_center_action_requests",
        type_="foreignkey",
    )
    op.drop_column("control_center_action_requests", "second_approved_by_id")
    op.drop_column("control_center_action_requests", "second_approved_at")
    op.drop_column("control_center_action_requests", "second_approval_required")
