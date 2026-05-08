from fastapi import FastAPI

from app.api.v1 import auth, shisha, users
from app.core.database import Base, engine

app = FastAPI(
    title="ShishaGuid API",
    version="0.1.0",
)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(shisha.router, prefix="/api/v1/shisha", tags=["shisha"])

@app.get("/health")
async def health():
    return {"response": "ok"}