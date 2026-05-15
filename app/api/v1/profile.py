from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.storage import promote_file
from app.models.user import User
from app.schemas.user import UserProfileResponse, UserProfileUpdate

router = APIRouter()


@router.get("/me", response_model=UserProfileResponse)
async def read_profile_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile_me(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if "nickname" in payload.model_fields_set:
        current_user.nickname = payload.nickname
    if "avatar_url" in payload.model_fields_set:
        current_user.avatar_url = (
            promote_file(payload.avatar_url, "profile") if payload.avatar_url else None
        )
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user
