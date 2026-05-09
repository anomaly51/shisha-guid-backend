import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import GoogleTokenRequest, TokenResponse

router = APIRouter()


@router.post("/google/token", response_model=TokenResponse)
async def exchange_google_token(
    payload: GoogleTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": payload.client_id,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": payload.code,
                "grant_type": "authorization_code",
                "redirect_uri": payload.redirect_uri,
            },
        )
        token_data = token_res.json()
        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data)

        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        user_info = user_res.json()
        if "error" in user_info or "id" not in user_info:
            raise HTTPException(status_code=400, detail=user_info)

    result = await db.execute(select(User).where(User.google_id == user_info["id"]))
    user = result.scalars().first()

    if not user:
        user = User(
            google_id=user_info["id"],
            email=user_info["email"],
            name=user_info.get("name"),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(data={"sub": str(user.id)}),
        token_type="bearer",
    )


@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}
