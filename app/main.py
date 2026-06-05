import asyncio
import hashlib
import logging
from email.utils import formatdate

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1 import agent, admin, auth, bowls, coals, profile, setups, tobaccos, upload
from app.core.config import settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.core.rate_limit import enforce_rate_limit
from app.core.startup import bootstrap_database
from app.core.storage import init_minio, minio_client
from sqlalchemy import text
import app.models  # noqa: F401

configure_logging()
logger = logging.getLogger(__name__)

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
app.state.active_requests = 0
app.state.shutdown_started = False

try:
    from prometheus_fastapi_instrumentator import Instrumentator

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
except Exception as exc:
    logger.info("Prometheus metrics disabled: %s", exc)

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
    app.state.active_requests += 1
    try:
        if request.url.path.startswith("/api/v1/") and not request.url.path.startswith("/api/v1/upload/media/"):
            await enforce_rate_limit(
                request,
                "api",
                settings.DEFAULT_RATE_LIMIT_PER_MINUTE,
            )

        response: Response = await call_next(request)
        if request.method != "GET" or response.status_code >= 400:
            return response

        path = request.url.path
        is_authenticated_request = bool(request.headers.get("authorization"))
        if is_authenticated_request and path.startswith("/api/v1/shisha/"):
            response.headers["Cache-Control"] = "private, no-store"
            if "ETag" in response.headers:
                del response.headers["ETag"]
            if "Last-Modified" in response.headers:
                del response.headers["Last-Modified"]
            return response

        if path.startswith("/api/v1/shisha/") or path.startswith("/api/v1/upload/media/"):
            response.headers.setdefault(
                "Cache-Control",
                "public, max-age=60, stale-while-revalidate=300",
            )
            if path.startswith((
                "/api/v1/shisha/tobaccos",
                "/api/v1/shisha/bowls",
                "/api/v1/shisha/coals",
                "/api/v1/shisha/kalouds",
                "/api/v1/shisha/coal-placements",
                "/api/v1/shisha/bowl-setup-types",
            )):
                etag_source = f"{path}?{request.url.query}"
                response.headers.setdefault("ETag", f'W/"{hashlib.sha1(etag_source.encode()).hexdigest()[:16]}"')
                response.headers.setdefault("Last-Modified", response.headers.get("date") or formatdate(usegmt=True))
        return response
    finally:
        app.state.active_requests = max(0, app.state.active_requests - 1)

@app.on_event("startup")
async def startup():
    await bootstrap_database(engine)
    init_minio()


@app.on_event("shutdown")
async def shutdown():
    app.state.shutdown_started = True
    deadline = asyncio.get_running_loop().time() + settings.SHUTDOWN_DRAIN_TIMEOUT_SECONDS
    while app.state.active_requests > 0 and asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.05)
    await engine.dispose()


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
    checks: dict[str, str] = {}
    healthy = True

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Database health check failed")
        checks["database"] = "error"
        healthy = False

    try:
        minio_client.bucket_exists(settings.MINIO_BUCKET)
        checks["minio"] = "ok"
    except Exception:
        logger.exception("MinIO health check failed")
        checks["minio"] = "error"
        healthy = False

    return JSONResponse(
        {
            "response": "ok",
            "status": "ok" if healthy else "degraded",
            "checks": checks,
            "smoke": "ci",
        },
        status_code=200 if healthy else 503,
    )
