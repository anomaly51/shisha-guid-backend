"""repair catalog columns required by current models

Revision ID: 20260721_0006
Revises: 20260528_0005
Create Date: 2026-07-21
"""

from alembic import op


revision = "20260721_0006"
down_revision = "20260528_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table_name in (
        "tobaccos",
        "coals",
        "kalouds",
        "bowls",
        "coal_placements",
        "bowl_setup_types",
    ):
        op.execute(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"
        )

    op.execute(
        "ALTER TABLE coal_placements ADD COLUMN IF NOT EXISTS coal_count INTEGER"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_coal_placements_deleted_at "
        "ON coal_placements (deleted_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bowl_setup_types_deleted_at "
        "ON bowl_setup_types (deleted_at)"
    )


def downgrade() -> None:
    # This migration repairs schema drift and may adopt pre-existing columns.
    # Dropping them would risk deleting production data.
    pass
