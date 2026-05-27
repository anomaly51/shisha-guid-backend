"""add tobacco brand

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27
"""
from alembic import op

revision = "20260527_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS brand VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tobaccos_lower_brand ON tobaccos (lower(brand))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tobaccos_lower_brand")
    op.drop_column("tobaccos", "brand")
