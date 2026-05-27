import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_optional_current_user
from app.core.storage import promote_file
from app.models.shisha import BowlSetup
from app.models.user import Notification, User, UserFollow
from app.schemas.user import (
    NotificationPageResponse,
    PublicUserResponse,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter()


async def _public_user_payload(
    db: AsyncSession,
    user: User,
    viewer: User | None,
) -> dict:
    setups_count = await db.scalar(
        select(func.count(BowlSetup.id)).where(BowlSetup.creator_id == user.id)
    )
    followers_count = await db.scalar(
        select(func.count(UserFollow.id)).where(UserFollow.followed_id == user.id)
    )
    following_count = await db.scalar(
        select(func.count(UserFollow.id)).where(UserFollow.follower_id == user.id)
    )
    is_following = False
    if viewer:
        is_following = bool(await db.scalar(
            select(UserFollow.id).where(
                UserFollow.follower_id == viewer.id,
                UserFollow.followed_id == user.id,
            )
        ))
    return {
        "id": user.id,
        "nickname": user.nickname,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "badges": user.badges,
        "setups_count": int(setups_count or 0),
        "followers_count": int(followers_count or 0),
        "following_count": int(following_count or 0),
        "is_following": is_following,
    }


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
        if payload.nickname:
            result = await db.execute(
                select(User.id).where(
                    func.lower(User.nickname) == payload.nickname.lower(),
                    User.id != current_user.id,
                )
            )
            if result.scalars().first():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Nickname is already taken",
                )
        current_user.nickname = payload.nickname
    if "avatar_url" in payload.model_fields_set:
        current_user.avatar_url = (
            promote_file(payload.avatar_url, "profile", str(current_user.id))
            if payload.avatar_url
            else None
        )
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/users/{user_id}", response_model=PublicUserResponse)
async def read_public_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_current_user),
):
    user = await db.get(User, user_id)
    if not user or user.is_banned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return await _public_user_payload(db, user, viewer)


@router.post("/users/{user_id}/follow", response_model=PublicUserResponse)
async def follow_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    user = await db.get(User, user_id)
    if not user or user.is_banned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    existing = await db.scalar(
        select(UserFollow.id).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.followed_id == user_id,
        )
    )
    if not existing:
        db.add(UserFollow(follower_id=current_user.id, followed_id=user_id))
        await db.commit()
    return await _public_user_payload(db, user, current_user)


@router.delete("/users/{user_id}/follow", response_model=PublicUserResponse)
async def unfollow_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    result = await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == current_user.id,
            UserFollow.followed_id == user_id,
        )
    )
    follow = result.scalars().first()
    if follow:
        await db.delete(follow)
        await db.commit()
    return await _public_user_payload(db, user, current_user)


@router.get("/notifications", response_model=NotificationPageResponse)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
    )
    unread_count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
    )
    return {"items": result.scalars().all(), "unread_count": int(unread_count or 0)}


@router.post("/notifications/read")
async def mark_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
    )
    for item in result.scalars().all():
        item.read_at = datetime.utcnow()
    await db.commit()
    return {"ok": True}
