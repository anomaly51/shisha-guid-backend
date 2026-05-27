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
            "ALTER TABLE users ALTER COLUMN badges TYPE JSONB USING badges::jsonb",
            "UPDATE users SET badges = '[]'::jsonb WHERE badges IS NULL OR jsonb_typeof(badges) <> 'array'",
            "ALTER TABLE bowl_setups DROP COLUMN IF EXISTS photo_urls",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS views_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS heaviness_score DOUBLE PRECISION",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS rating_average DOUBLE PRECISION NOT NULL DEFAULT 0",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS rating_count INTEGER NOT NULL DEFAULT 0",
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
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS package_grams INTEGER",
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS strength INTEGER",
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
        ):
            await conn.execute(text(statement))

        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_tobaccos_lower_name ON tobaccos (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_coals_lower_name ON coals (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_created_at ON bowl_setups (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_views_count ON bowl_setups (views_count DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_heaviness_score ON bowl_setups (heaviness_score)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_rating_average ON bowl_setups (rating_average DESC)",
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
