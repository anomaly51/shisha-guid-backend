import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_user_from_refresh_token,
)
from app.models.user import User
from app.schemas.auth import TokenRefreshRequest, TokenResponse

router = APIRouter()


def _is_configured_admin(email: str):
    admin_emails = {
        configured_email.strip().lower()
        for configured_email in settings.ADMIN_EMAILS.split(",")
        if configured_email.strip()
    }
    return email.lower() in admin_emails


async def _nickname_exists(db: AsyncSession, nickname: str) -> bool:
    result = await db.execute(
        select(User.id).where(User.nickname.ilike(nickname.strip())).limit(1)
    )
    return result.scalars().first() is not None


@router.post("/google/token", response_model=TokenResponse)
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

        if user_info.get("verified_email") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Google email is not verified",
            )

    result = await db.execute(select(User).where(User.google_id == user_info["id"]))
    user = result.scalars().first()

    if not user:
        nickname = (user_info.get("name") or "").strip() or None
        if nickname and await _nickname_exists(db, nickname):
            nickname = None
        user = User(
            google_id=user_info["id"],
            email=user_info["email"],
            nickname=nickname,
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
        "refresh_token": create_refresh_token(data={"sub": str(user.id)}),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_from_refresh_token(payload.refresh_token, db)
    return {
        "access_token": create_access_token(data={"sub": str(user.id)}),
        "refresh_token": create_refresh_token(data={"sub": str(user.id)}),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout")
async def logout():
    return {"message": "Successfully logged out"}
