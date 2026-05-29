from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.core.database import Base


PRICED_COMPONENT_TABLES = ("tobaccos", "coals", "kalouds", "bowls")
CATALOG_TABLES = (
    "tobaccos",
    "coals",
    "kalouds",
    "bowls",
    "coal_placements",
    "bowl_setup_types",
)


async def bootstrap_database(engine: AsyncEngine) -> None:
    if not settings.RUN_SCHEMA_BOOTSTRAP:
        return

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        for statement in (
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR NOT NULL DEFAULT 'user'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS badges JSON NOT NULL DEFAULT '[]'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS streak_days INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS score INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ALTER COLUMN badges TYPE JSONB USING badges::jsonb",
            "UPDATE users SET badges = '[]'::jsonb WHERE badges IS NULL OR jsonb_typeof(badges) <> 'array'",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS views_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS heaviness_score DOUBLE PRECISION",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS rating_average DOUBLE PRECISION NOT NULL DEFAULT 0",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS rating_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS photo_urls VARCHAR[] DEFAULT '{}'",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS tags VARCHAR[] DEFAULT '{}'",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS source_setup_id UUID REFERENCES bowl_setups(id)",
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS setups_count INTEGER NOT NULL DEFAULT 0",
            "UPDATE bowl_setups SET views_count = 0 WHERE views_count IS NULL",
            """
            UPDATE bowl_setups
            SET heaviness_score = stats.score
            FROM (
                SELECT
                    bst.bowl_setup_id,
                    LEAST(
                        10,
                        GREATEST(
                            0,
                            SUM(COALESCE(t.strength, 5) * bst.percentage)::DOUBLE PRECISION
                            / NULLIF(SUM(bst.percentage), 0)
                        )
                    ) AS score
                FROM bowl_setup_tobaccos bst
                JOIN tobaccos t ON t.id = bst.tobacco_id
                GROUP BY bst.bowl_setup_id
            ) stats
            WHERE bowl_setups.id = stats.bowl_setup_id
              AND bowl_setups.heaviness_score IS NULL
            """,
            "UPDATE bowl_setups SET heaviness_score = 5 WHERE heaviness_score IS NULL",
            "UPDATE bowl_setups SET rating_average = 0 WHERE rating_average IS NULL",
            "UPDATE bowl_setups SET rating_count = 0 WHERE rating_count IS NULL",
            "ALTER TABLE bowl_setups ALTER COLUMN views_count SET DEFAULT 0",
            "ALTER TABLE bowl_setups ALTER COLUMN views_count SET NOT NULL",
            "ALTER TABLE bowl_setups ALTER COLUMN rating_average SET DEFAULT 0",
            "ALTER TABLE bowl_setups ALTER COLUMN rating_average SET NOT NULL",
            "ALTER TABLE bowl_setups ALTER COLUMN rating_count SET DEFAULT 0",
            "ALTER TABLE bowl_setups ALTER COLUMN rating_count SET NOT NULL",
            "ALTER TABLE bowl_setups ALTER COLUMN version SET DEFAULT 1",
            "ALTER TABLE bowl_setups ALTER COLUMN version SET NOT NULL",
        ):
            await conn.execute(text(statement))

        for table_name in PRICED_COMPONENT_TABLES:
            for statement in (
                f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS price INTEGER NOT NULL DEFAULT 0",
                f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS price_currency VARCHAR NOT NULL DEFAULT 'UAH'",
                f"UPDATE {table_name} SET price = 0 WHERE price IS NULL",
                f"UPDATE {table_name} SET price_currency = 'UAH' WHERE price_currency IS NULL",
                f"ALTER TABLE {table_name} ALTER COLUMN price SET DEFAULT 0",
                f"ALTER TABLE {table_name} ALTER COLUMN price SET NOT NULL",
                f"ALTER TABLE {table_name} ALTER COLUMN price_currency SET DEFAULT 'UAH'",
                f"ALTER TABLE {table_name} ALTER COLUMN price_currency SET NOT NULL",
            ):
                await conn.execute(text(statement))

        for table_name in CATALOG_TABLES:
            await conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")
            )

        for statement in (
            "ALTER TABLE coals ADD COLUMN IF NOT EXISTS coals_per_package INTEGER",
            "ALTER TABLE bowls ADD COLUMN IF NOT EXISTS capacity_grams INTEGER",
            "ALTER TABLE bowls ADD COLUMN IF NOT EXISTS bowl_type VARCHAR NOT NULL DEFAULT 'traditional'",
            "UPDATE bowls SET bowl_type = 'traditional' WHERE bowl_type NOT IN ('traditional', 'phunnel')",
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS brand VARCHAR",
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS package_grams INTEGER",
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS strength INTEGER",
            """
            UPDATE tobaccos
            SET setups_count = stats.setup_count
            FROM (
                SELECT tobacco_id, COUNT(DISTINCT bowl_setup_id)::INTEGER AS setup_count
                FROM bowl_setup_tobaccos
                GROUP BY tobacco_id
            ) stats
            WHERE tobaccos.id = stats.tobacco_id
            """,
            "ALTER TABLE coal_placements ADD COLUMN IF NOT EXISTS coal_count INTEGER",
            "ALTER TABLE bowl_setup_reviews ALTER COLUMN rating TYPE DOUBLE PRECISION USING rating::DOUBLE PRECISION",
            """
            UPDATE bowl_setups
            SET
                rating_average = stats.average,
                rating_count = stats.review_count
            FROM (
                SELECT
                    bowl_setup_id,
                    ROUND(AVG(rating)::NUMERIC, 1)::DOUBLE PRECISION AS average,
                    COUNT(*)::INTEGER AS review_count
                FROM bowl_setup_reviews
                GROUP BY bowl_setup_id
            ) stats
            WHERE bowl_setups.id = stats.bowl_setup_id
            """,
            """
            UPDATE bowl_setups
            SET rating_average = 0, rating_count = 0
            WHERE NOT EXISTS (
                SELECT 1
                FROM bowl_setup_reviews
                WHERE bowl_setup_reviews.bowl_setup_id = bowl_setups.id
            )
            """,
        ):
            await conn.execute(text(statement))

        for statement in (
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'ck_bowls_bowl_type'
                ) THEN
                    ALTER TABLE bowls
                    ADD CONSTRAINT ck_bowls_bowl_type
                    CHECK (bowl_type IN ('traditional', 'phunnel'));
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_badges_array'
                ) THEN
                    ALTER TABLE users
                    ADD CONSTRAINT ck_users_badges_array
                    CHECK (jsonb_typeof(badges) = 'array');
                END IF;
            END $$;
            """,
            """
            CREATE TABLE IF NOT EXISTS user_follows (
                id UUID PRIMARY KEY,
                follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                followed_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_user_follow_pair UNIQUE (follower_id, followed_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS setup_bookmarks (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_setup_bookmark_user_setup UNIQUE (user_id, bowl_setup_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
                bowl_setup_id UUID REFERENCES bowl_setups(id) ON DELETE CASCADE,
                type VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                body TEXT,
                read_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bowl_setup_versions (
                id UUID PRIMARY KEY,
                bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                snapshot JSONB NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bowl_setup_contributors (
                id UUID PRIMARY KEY,
                bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_setup_contributor_user UNIQUE (bowl_setup_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bowl_setup_comments (
                id UUID PRIMARY KEY,
                bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
                creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS bowl_setup_likes (
                id UUID PRIMARY KEY,
                bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_bowl_setup_like_user UNIQUE (bowl_setup_id, user_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS setup_collections (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(80) NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_setup_collection_user_name UNIQUE (user_id, name)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS setup_collection_items (
                id UUID PRIMARY KEY,
                collection_id UUID NOT NULL REFERENCES setup_collections(id) ON DELETE CASCADE,
                bowl_setup_id UUID NOT NULL REFERENCES bowl_setups(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_collection_setup UNIQUE (collection_id, bowl_setup_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS review_replies (
                id UUID PRIMARY KEY,
                review_id UUID NOT NULL REFERENCES bowl_setup_reviews(id) ON DELETE CASCADE,
                creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """,
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
            """,
            """
            CREATE TABLE IF NOT EXISTS user_favorite_tobaccos (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tobacco_id UUID NOT NULL REFERENCES tobaccos(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ DEFAULT now(),
                CONSTRAINT uq_user_favorite_tobacco UNIQUE (user_id, tobacco_id)
            )
            """,
        ):
            await conn.execute(text(statement))

        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_tobaccos_lower_name ON tobaccos (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_tobaccos_lower_brand ON tobaccos (lower(brand))",
            "CREATE INDEX IF NOT EXISTS ix_coals_lower_name ON coals (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_created_at ON bowl_setups (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_featured_created ON bowl_setups (is_featured DESC, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_tags_gin ON bowl_setups USING GIN (tags)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_views_count ON bowl_setups (views_count DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_heaviness_score ON bowl_setups (heaviness_score)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_rating_average ON bowl_setups (rating_average DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_lower_name ON bowl_setups (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_notifications_user_read_created ON notifications (user_id, read_at, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_user_follows_follower_id ON user_follows (follower_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_follows_followed_id ON user_follows (followed_id)",
            "CREATE INDEX IF NOT EXISTS ix_setup_bookmarks_user_id ON setup_bookmarks (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_versions_setup_version ON bowl_setup_versions (bowl_setup_id, version DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_comments_setup_created ON bowl_setup_comments (bowl_setup_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_comments_creator_id ON bowl_setup_comments (creator_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_likes_setup_id ON bowl_setup_likes (bowl_setup_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_likes_user_id ON bowl_setup_likes (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_setup_contributors_setup ON bowl_setup_contributors (bowl_setup_id)",
            "CREATE INDEX IF NOT EXISTS ix_setup_contributors_user ON bowl_setup_contributors (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_setup_collections_user ON setup_collections (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_setup_collection_items_setup ON setup_collection_items (bowl_setup_id)",
            "CREATE INDEX IF NOT EXISTS ix_review_replies_review_created ON review_replies (review_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_reports_status_created ON reports (status, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_reports_target ON reports (target_type, target_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_favorite_tobaccos_user ON user_favorite_tobaccos (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_user_favorite_tobaccos_tobacco ON user_favorite_tobaccos (tobacco_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_source_setup_id ON bowl_setups (source_setup_id)",
            "CREATE INDEX IF NOT EXISTS ix_users_last_seen_at ON users (last_seen_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_users_last_active_at ON users (last_active_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_users_score ON users (score DESC)",
            "CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)",
            "CREATE INDEX IF NOT EXISTS ix_users_badges_gin ON users USING GIN (badges)",
            "CREATE INDEX IF NOT EXISTS ix_tobaccos_deleted_at ON tobaccos (deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_coals_deleted_at ON coals (deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_kalouds_deleted_at ON kalouds (deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_bowls_deleted_at ON bowls (deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_coal_placements_deleted_at ON coal_placements (deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_types_deleted_at ON bowl_setup_types (deleted_at)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_tobaccos_setup_id ON bowl_setup_tobaccos (bowl_setup_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_tobaccos_tobacco_id ON bowl_setup_tobaccos (tobacco_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_views_setup_ip ON bowl_setup_views (bowl_setup_id, ip_address)",
        ):
            await conn.execute(text(statement))
