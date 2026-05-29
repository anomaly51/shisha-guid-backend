"""add social features

Revision ID: 20260528_0002
Revises: 20260527_0001
Create Date: 2026-05-28
"""
from alembic import op

revision = "20260528_0002"
down_revision = "20260527_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ")
    op.execute("ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS source_setup_id UUID REFERENCES bowl_setups(id)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bowl_setup_comments (
            id UUID PRIMARY KEY,
            bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
            creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bowl_setup_likes (
            id UUID PRIMARY KEY,
            bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_bowl_setup_like_user UNIQUE (bowl_setup_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_bowl_setup_comments_setup_created ON bowl_setup_comments (bowl_setup_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bowl_setup_comments_creator_id ON bowl_setup_comments (creator_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bowl_setup_likes_setup_id ON bowl_setup_likes (bowl_setup_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bowl_setup_likes_user_id ON bowl_setup_likes (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bowl_setups_source_setup_id ON bowl_setups (source_setup_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_last_seen_at ON users (last_seen_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_last_seen_at")
    op.execute("DROP INDEX IF EXISTS ix_bowl_setups_source_setup_id")
    op.execute("DROP INDEX IF EXISTS ix_bowl_setup_likes_user_id")
    op.execute("DROP INDEX IF EXISTS ix_bowl_setup_likes_setup_id")
    op.execute("DROP INDEX IF EXISTS ix_bowl_setup_comments_creator_id")
    op.execute("DROP INDEX IF EXISTS ix_bowl_setup_comments_setup_created")
    op.execute("DROP TABLE IF EXISTS bowl_setup_likes")
    op.execute("DROP TABLE IF EXISTS bowl_setup_comments")
    op.execute("ALTER TABLE bowl_setups DROP COLUMN IF EXISTS source_setup_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_seen_at")
