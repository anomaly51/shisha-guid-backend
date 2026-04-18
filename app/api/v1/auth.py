import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User

router = APIRouter()

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"


@router.get("/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code"
        f"&client_id={settings.GOOGLE_CLIENT_ID}&redirect_uri={redirect_uri}"
        f"&scope=openid%20profile%20email&access_type=offline"
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
async def google_callback(
    request: Request, code: str, db: AsyncSession = Depends(get_db)
):
    redirect_uri = request.url_for("google_callback")
    return await process_google_auth(code, str(redirect_uri), db)


@router.post("/google/token")
async def google_swagger_token(
    request: Request,
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(None),
    code_verifier: str = Form(None),  # Вот здесь мы ловим верификатор от Swagger!
    db: AsyncSession = Depends(get_db),
):
    token_data = await process_google_auth(code, redirect_uri, db, code_verifier)
    return {"access_token": token_data["access_token"], "token_type": "bearer"}


async def process_google_auth(
    code: str, redirect_uri: str, db: AsyncSession, code_verifier: str = None
):
    async with httpx.AsyncClient() as client:
        # Собираем данные
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        # Прикрепляем верификатор, если он есть
        if code_verifier:
            data["code_verifier"] = code_verifier

        token_response = await client.post(GOOGLE_TOKEN_URL, data=data)
        token_data = token_response.json()

        if "error" in token_data:
            print(
                f"\n\n=== ОШИБКА ОТ GOOGLE (TOKEN) ===\n{token_data}\n================================\n"
            )
            raise HTTPException(
                status_code=400, detail=f"Google Token Error: {token_data}"
            )

        user_info_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data.get('access_token')}"},
        )
        user_info = user_info_response.json()

        if "error" in user_info or "id" not in user_info:
            print(
                f"\n\n=== ОШИБКА ОТ GOOGLE (PROFILE) ===\n{user_info}\n================================\n"
            )
            raise HTTPException(
                status_code=400, detail=f"Google Profile Error: {user_info}"
            )

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

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
