import httpx
from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User

router = APIRouter()


def _is_configured_admin(email: str):
    admin_emails = {
        configured_email.strip().lower()
        for configured_email in settings.ADMIN_EMAILS.split(",")
        if configured_email.strip()
    }
    return email.lower() in admin_emails


@router.post("/google/token")
async def exchange_google_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    code_verifier: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    async with httpx.AsyncClient() as client:
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
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
            nickname=user_info.get("name"),
            avatar_url=user_info.get("picture"),
            role="admin" if _is_configured_admin(user_info["email"]) else "user",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        changed = False
        if not user.avatar_url and user_info.get("picture"):
            user.avatar_url = user_info.get("picture")
            changed = True
        if _is_configured_admin(user.email) and user.role != "admin":
            user.role = "admin"
            changed = True
        if changed:
            db.add(user)
            await db.commit()
            await db.refresh(user)

    if user.is_banned:
        raise HTTPException(status_code=403, detail="User account is banned")

    return {
        "access_token": create_access_token(data={"sub": str(user.id)}),
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}
