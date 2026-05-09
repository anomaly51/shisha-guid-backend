from fastapi import FastAPI

from app.api.v1 import auth, shisha, user, users  # <-- Изменили users на user
from app.core.config import settings
from app.core.database import Base, engine
from app.models import User  # <-- Убрали импорт Tobacco

app = FastAPI(
    title="ShishaGuid API",
    version="0.1.0",
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


app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(shisha.router, prefix="/api/v1/shisha", tags=["shisha"])


@app.get("/health")
async def health():
    return {"response": "ok"}
