"""deeper social features

Revision ID: 20260528_0004
Revises: 20260528_0003
Create Date: 2026-05-28
"""
from alembic import op

revision = "20260528_0004"
down_revision = "20260528_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_days INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS score INTEGER NOT NULL DEFAULT 0")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_score ON users (score DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bowl_setup_contributors (
            id UUID PRIMARY KEY,
            bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_setup_contributor_user UNIQUE (bowl_setup_id, user_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_setup_contributors_setup ON bowl_setup_contributors (bowl_setup_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_setup_contributors_user ON bowl_setup_contributors (user_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS setup_collections (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(80) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_setup_collection_user_name UNIQUE (user_id, name)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS setup_collection_items (
            id UUID PRIMARY KEY,
            collection_id UUID NOT NULL REFERENCES setup_collections(id) ON DELETE CASCADE,
            bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_collection_setup UNIQUE (collection_id, bowl_setup_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_setup_collections_user ON setup_collections (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_setup_collection_items_setup ON setup_collection_items (bowl_setup_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS review_replies (
            id UUID PRIMARY KEY,
            review_id UUID NOT NULL REFERENCES bowl_setup_reviews(id) ON DELETE CASCADE,
            creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_review_replies_review_created ON review_replies (review_id, created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id UUID PRIMARY KEY,
            target_type VARCHAR(32) NOT NULL,
            target_id UUID NOT NULL,
            reporter_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reason TEXT NOT NULL,
            status VARCHAR(24) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ DEFAULT now(),
            resolved_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_status_created ON reports (status, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_reports_target ON reports (target_type, target_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_favorite_tobaccos (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tobacco_id UUID NOT NULL REFERENCES tobaccos(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_user_favorite_tobacco UNIQUE (user_id, tobacco_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_favorite_tobaccos_user ON user_favorite_tobaccos (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_favorite_tobaccos_tobacco ON user_favorite_tobaccos (tobacco_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_user_favorite_tobaccos_tobacco")
    op.execute("DROP INDEX IF EXISTS ix_user_favorite_tobaccos_user")
    op.execute("DROP TABLE IF EXISTS user_favorite_tobaccos")
    op.execute("DROP INDEX IF EXISTS ix_reports_target")
    op.execute("DROP INDEX IF EXISTS ix_reports_status_created")
    op.execute("DROP TABLE IF EXISTS reports")
    op.execute("DROP INDEX IF EXISTS ix_review_replies_review_created")
    op.execute("DROP TABLE IF EXISTS review_replies")
    op.execute("DROP INDEX IF EXISTS ix_setup_collection_items_setup")
    op.execute("DROP INDEX IF EXISTS ix_setup_collections_user")
    op.execute("DROP TABLE IF EXISTS setup_collection_items")
    op.execute("DROP TABLE IF EXISTS setup_collections")
    op.execute("DROP INDEX IF EXISTS ix_setup_contributors_user")
    op.execute("DROP INDEX IF EXISTS ix_setup_contributors_setup")
    op.execute("DROP TABLE IF EXISTS bowl_setup_contributors")
    op.execute("DROP INDEX IF EXISTS ix_users_last_active_at")
    op.execute("DROP INDEX IF EXISTS ix_users_score")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS score")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS streak_days")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_active_at")
