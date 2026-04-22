from fastapi import FastAPI
from app.api.v1 import auth, users
from app.core.database import engine, Base
from app.core.config import settings # Добавили импорт наших настроек из .env

app = FastAPI(
    title="ShishaGuid API",
    description="Backend API with Google OAuth2",
    version="0.1.0",
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
    swagger_ui_init_oauth={
        "usePkceWithAuthorizationCodeGrant": True,
        "clientId": settings.GOOGLE_CLIENT_ID, 
        "scopes": "openid profile email" 
    }
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])

@app.get("/")
async def root():
    return {"message": "Welcome to ShishaGuid API"}