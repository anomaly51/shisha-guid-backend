"""catalog content improvements

Revision ID: 20260528_0003
Revises: 20260528_0002
Create Date: 2026-05-28
"""
from alembic import op

revision = "20260528_0003"
down_revision = "20260528_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS tags VARCHAR[] DEFAULT '{}'")
    op.execute("ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS setups_count INTEGER NOT NULL DEFAULT 0")
    op.execute(
        """
        UPDATE tobaccos
        SET setups_count = stats.setup_count
        FROM (
            SELECT tobacco_id, COUNT(DISTINCT bowl_setup_id)::INTEGER AS setup_count
            FROM bowl_setup_tobaccos
            GROUP BY tobacco_id
        ) stats
        WHERE tobaccos.id = stats.tobacco_id
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_bowl_setups_featured_created ON bowl_setups (is_featured DESC, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bowl_setups_tags_gin ON bowl_setups USING GIN (tags)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tobaccos_setups_count ON tobaccos (setups_count DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tobaccos_setups_count")
    op.execute("DROP INDEX IF EXISTS ix_bowl_setups_tags_gin")
    op.execute("DROP INDEX IF EXISTS ix_bowl_setups_featured_created")
    op.execute("ALTER TABLE tobaccos DROP COLUMN IF EXISTS setups_count")
    op.execute("ALTER TABLE bowl_setups DROP COLUMN IF EXISTS is_featured")
    op.execute("ALTER TABLE bowl_setups DROP COLUMN IF EXISTS tags")
