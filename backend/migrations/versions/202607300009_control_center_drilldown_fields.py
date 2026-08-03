"""add lossless Google Ads drill-down fields

Revision ID: 202607300009
Revises: 202607300008
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607300009"
down_revision: str | None = "202607300008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "control_center_ads",
        sa.Column(
            "final_urls",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "control_center_assets",
        sa.Column("image_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "control_center_ad_asset_links",
        sa.Column("resource_name", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade intentionally disabled: removing drill-down fields can discard synchronized Google data."
    )
