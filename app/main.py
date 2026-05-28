import hashlib
from email.utils import formatdate

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1 import agent, admin, auth, bowls, coals, profile, setups, tobaccos, upload
from app.core.config import settings
from app.core.database import engine
from app.core.startup import bootstrap_database
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

@app.on_event("startup")
async def startup():
    await bootstrap_database(engine)
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
