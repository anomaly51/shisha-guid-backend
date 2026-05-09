from fastapi import FastAPI

from app.api.v1 import auth, profile, shisha  
from app.core.config import settings
from app.core.database import Base, engine

from app.models import (
    Bowl,
    BowlSetup,
    BowlSetupTobacco,
    BowlSetupType,
    Coal,
    CoalPlacement,
    Kaloud,
    Tobacco,
    User,
)

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


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(
    profile.router, prefix="/api/v1/profile", tags=["profile"]
) 
app.include_router(shisha.router, prefix="/api/v1/shisha", tags=["shisha"])


@app.get("/")
async def root():
    return {"message": "Welcome to API"}


@app.get("/health")
async def health():
    return {"response": "ok"}
