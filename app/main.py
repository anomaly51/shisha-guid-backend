from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from app.api.v1 import agent, admin, auth, bowls, coals, profile, setups, tobaccos, upload
from app.core.config import settings
from app.core.database import Base, engine
from app.core.storage import init_minio
import app.models  # noqa: F401

app = FastAPI(
    title="ShishaGuid API",
    version="0.1.0",
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings.GOOGLE_CLIENT_ID,
        "scopes": "openid profile email",
    },
)

app.add_middleware(GZipMiddleware, minimum_size=1024)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://shisha-guid.api-api-api.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_public_cache_headers(request: Request, call_next):
    response: Response = await call_next(request)
    if request.method != "GET" or response.status_code >= 400:
        return response

    path = request.url.path
    if path.startswith("/api/v1/shisha/") or path.startswith("/api/v1/upload/media/"):
        response.headers.setdefault(
            "Cache-Control",
            "public, max-age=60, stale-while-revalidate=300",
        )
    return response

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR")
        )
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "role VARCHAR NOT NULL DEFAULT 'user'"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "is_banned BOOLEAN NOT NULL DEFAULT false"
            )
        )
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "badges JSON NOT NULL DEFAULT '[]'"
            )
        )
        await conn.execute(
            text("ALTER TABLE bowl_setups DROP COLUMN IF EXISTS photo_urls")
        )
        await conn.execute(
            text(
                "ALTER TABLE bowl_setups ADD COLUMN IF NOT EXISTS "
                "views_count INTEGER NOT NULL DEFAULT 0"
            )
        )
        await conn.execute(
            text("UPDATE bowl_setups SET views_count = 0 WHERE views_count IS NULL")
        )
        await conn.execute(
            text("ALTER TABLE bowl_setups ALTER COLUMN views_count SET DEFAULT 0")
        )
        await conn.execute(
            text("ALTER TABLE bowl_setups ALTER COLUMN views_count SET NOT NULL")
        )
        for table_name in ("tobaccos", "coals", "kalouds", "bowls"):
            await conn.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    "ADD COLUMN IF NOT EXISTS price INTEGER NOT NULL DEFAULT 0"
                )
            )
            await conn.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    "ADD COLUMN IF NOT EXISTS price_currency VARCHAR NOT NULL DEFAULT 'UAH'"
                )
            )
            await conn.execute(text(f"UPDATE {table_name} SET price = 0 WHERE price IS NULL"))
            await conn.execute(
                text(
                    f"UPDATE {table_name} "
                    "SET price_currency = 'UAH' WHERE price_currency IS NULL"
                )
            )
            await conn.execute(
                text(f"ALTER TABLE {table_name} ALTER COLUMN price SET DEFAULT 0")
            )
            await conn.execute(
                text(f"ALTER TABLE {table_name} ALTER COLUMN price SET NOT NULL")
            )
            await conn.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    "ALTER COLUMN price_currency SET DEFAULT 'UAH'"
                )
            )
            await conn.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    "ALTER COLUMN price_currency SET NOT NULL"
                )
            )
        await conn.execute(
            text("ALTER TABLE coals ADD COLUMN IF NOT EXISTS coals_per_package INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE bowls ADD COLUMN IF NOT EXISTS capacity_grams INTEGER")
        )
        await conn.execute(
            text(
                "ALTER TABLE bowls ADD COLUMN IF NOT EXISTS "
                "bowl_type VARCHAR NOT NULL DEFAULT 'traditional'"
            )
        )
        await conn.execute(
            text("ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS package_grams INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE tobaccos ADD COLUMN IF NOT EXISTS strength INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE coal_placements ADD COLUMN IF NOT EXISTS coal_count INTEGER")
        )
        await conn.execute(
            text(
                "ALTER TABLE bowl_setup_reviews "
                "ALTER COLUMN rating TYPE DOUBLE PRECISION "
                "USING rating::DOUBLE PRECISION"
            )
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS ix_tobaccos_lower_name ON tobaccos (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_coals_lower_name ON coals (lower(name))",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_created_at ON bowl_setups (created_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setups_views_count ON bowl_setups (views_count DESC)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_tobaccos_setup_id ON bowl_setup_tobaccos (setup_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_tobaccos_tobacco_id ON bowl_setup_tobaccos (tobacco_id)",
            "CREATE INDEX IF NOT EXISTS ix_bowl_setup_views_setup_ip ON bowl_setup_views (setup_id, ip_hash)",
        ):
            await conn.execute(text(index_sql))
    init_minio()


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["profile"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(
    tobaccos.router, prefix="/api/v1/shisha/tobaccos", tags=["shisha-tobacco"]
)
app.include_router(bowls.router, prefix="/api/v1/shisha/bowls", tags=["shisha-bowl"])
app.include_router(coals.router, prefix="/api/v1/shisha", tags=["shisha-coal-kaloud"])
app.include_router(setups.router, prefix="/api/v1/shisha", tags=["shisha-setups"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])


@app.get("/")
async def root():
    return {"message": "Welcome to API"}


@app.get("/health")
async def health():
    return {"response": "ok"}
