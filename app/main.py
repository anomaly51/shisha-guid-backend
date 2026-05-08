from fastapi import FastAPI

from app.api.v1 import auth, user  # <-- Изменили users на user
from app.core.config import settings
from app.core.database import Base, engine
from app.models import User  # <-- Убрали импорт Tobacco

app = FastAPI(
    title="ShishaGuid API",
    description="Backend API with Google OAuth2",
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


# Подключаем только оставшиеся роутеры
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user.router, prefix="/api/v1/users", tags=["users"])


@app.get("/")
async def root():
    return {"message": "Welcome to API"}
