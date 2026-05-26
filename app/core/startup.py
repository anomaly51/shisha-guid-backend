from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.database import Base


PRICED_COMPONENT_TABLES = ("tobaccos", "coals", "kalouds", "bowls")


async def bootstrap_database(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        for statement in (
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR NOT NULL DEFAULT 'user'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT false",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS badges JSON NOT NULL DEFAULT '[]'",
            "ALTER TABLE bowl_setups DROP COLUMN IF EXISTS photo_urls",
            "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS views_count INTEGER NOT NULL DEFAULT 0",
            "UPDATE bowl_setups SET views_count = 0 WHERE views_count IS NULL",
            "ALTER TABLE bowl_setups ALTER COLUMN views_count SET DEFAULT 0",
            "ALTER TABLE bowl_setups ALTER COLUMN views_count SET NOT NULL",
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

        for statement in (
            "ALTER TABLE coals ADD COLUMN IF NOT EXISTS coals_per_package INTEGER",
            "ALTER TABLE bowls ADD COLUMN IF NOT EXISTS capacity_grams INTEGER",
            "ALTER TABLE bowls ADD COLUMN IF NOT EXISTS bowl_type VARCHAR NOT NULL DEFAULT 'traditional'",
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS package_grams INTEGER",
            "ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS strength INTEGER",
            "ALTER TABLE coal_placements ADD COLUMN IF NOT EXISTS coal_count INTEGER",
            "ALTER TABLE bowl_setup_reviews ALTER COLUMN rating TYPE DOUBLE PRECISION USING rating::DOUBLE PRECISION",
        ):
            await conn.execute(text(statement))

        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_tobaccos_lower_name ON tobaccos (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_coals_lower_name ON coals (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_created_at ON bowl_setups (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_views_count ON bowl_setups (views_count DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_tobaccos_setup_id ON bowl_setup_tobaccos (bowl_setup_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_tobaccos_tobacco_id ON bowl_setup_tobaccos (tobacco_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_views_setup_ip ON bowl_setup_views (bowl_setup_id, ip_address)",
        ):
            await conn.execute(text(statement))
