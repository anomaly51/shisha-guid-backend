import httpx
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User

router = APIRouter()


@router.post("/google/token")
async def exchange_google_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    client_id: str = Form(None),
    redirect_uri: str = Form(...),
    code_verifier: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    async with httpx.AsyncClient() as client:
        data = {
            "client_id": client_id or settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": grant_type,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        token_res = await client.post("https://oauth2.googleapis.com/token", data=data)
        token_data = token_res.json()

        if "error" in token_data:
            print("❌ GOOGLE TOKEN ERROR:", token_data)
            raise HTTPException(status_code=400, detail=token_data)

        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v1/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        user_info = user_res.json()

        if "error" in user_info or "id" not in user_info:
            print("❌ GOOGLE USERINFO ERROR:", user_info)
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

    return {
        "access_token": create_access_token(data={"sub": str(user.id)}),
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}
