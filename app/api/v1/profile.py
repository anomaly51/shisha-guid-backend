import uuid
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import _get_user_from_token, get_current_user, get_optional_current_user
from app.crud import shisha as crud
from app.core.storage import promote_file
from app.models.shisha import BowlSetup, BowlSetupReview, BowlSetupTobacco, Tobacco
from app.models.user import (
    Notification,
    SetupCollection,
    SetupCollectionItem,
    User,
    UserFavoriteTobacco,
    UserFollow,
)
from app.schemas.shisha import BowlSetupPageResponse, TobaccoResponse
from app.schemas.user import (
    NotificationPageResponse,
    PublicUserResponse,
    SetupCollectionCreate,
    SetupCollectionResponse,
    UserProfileResponse,
    UserProfileUpdate,
    UserActivityResponse,
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
    is_followed_by = False
    if viewer:
        is_following = bool(await db.scalar(
            select(UserFollow.id).where(
                UserFollow.follower_id == viewer.id,
                UserFollow.followed_id == user.id,
            )
        ))
        is_followed_by = bool(await db.scalar(
            select(UserFollow.id).where(
                UserFollow.follower_id == user.id,
                UserFollow.followed_id == viewer.id,
            )
        ))
    return {
        "id": user.id,
        "nickname": user.nickname,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "badges": user.badges,
        "last_seen_at": user.last_seen_at,
        "setups_count": int(setups_count or 0),
        "followers_count": int(followers_count or 0),
        "following_count": int(following_count or 0),
        "is_following": is_following,
        "is_followed_by": is_followed_by,
        "last_active_at": user.last_active_at,
        "streak_days": user.streak_days,
        "score": user.score,
    }


@router.get("/me", response_model=UserProfileResponse)
async def read_profile_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.last_seen_at = datetime.utcnow()
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.get("/activity", response_model=list[UserActivityResponse])
async def read_profile_activity(
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_limit = max(1, min(limit, 100))
    created_result = await db.execute(
        select(BowlSetup)
        .where(BowlSetup.creator_id == current_user.id)
        .order_by(BowlSetup.created_at.desc())
        .limit(safe_limit)
    )
    reviewed_result = await db.execute(
        select(BowlSetupReview, BowlSetup)
        .join(BowlSetup, BowlSetup.id == BowlSetupReview.bowl_setup_id)
        .where(BowlSetupReview.creator_id == current_user.id)
        .order_by(BowlSetupReview.created_at.desc())
        .limit(safe_limit)
    )

    items: list[dict] = []
    for setup in created_result.scalars().all():
        items.append({
            "id": f"setup:{setup.id}",
            "type": "setup_cloned" if setup.source_setup_id else "setup_created",
            "title": f"Клонировал забивку {setup.name}" if setup.source_setup_id else f"Создал забивку {setup.name}",
            "setup_id": setup.id,
            "created_at": setup.created_at,
        })
    for review, setup in reviewed_result.all():
        items.append({
            "id": f"review:{review.id}",
            "type": "review_created",
            "title": f"Оставил отзыв на {setup.name}",
            "setup_id": setup.id,
            "created_at": review.created_at,
        })

    return sorted(items, key=lambda item: item["created_at"], reverse=True)[:safe_limit]


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


@router.get("/users", response_model=list[PublicUserResponse])
async def search_public_users(
    nickname: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_current_user),
):
    safe_limit = max(1, min(limit, 50))
    query = select(User).where(User.is_banned.is_(False))
    if nickname:
        normalized = f"%{nickname.strip()}%"
        query = query.where(User.nickname.ilike(normalized))
    query = query.order_by(func.lower(User.nickname).nullslast(), User.email).limit(safe_limit)
    result = await db.execute(query)
    return [
        await _public_user_payload(db, user, viewer)
        for user in result.scalars().all()
    ]


@router.get("/top-authors", response_model=list[PublicUserResponse])
async def get_top_authors(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_current_user),
):
    safe_limit = max(1, min(limit, 50))
    result = await db.execute(
        select(User, func.count(BowlSetup.id).label("setups_total"))
        .join(BowlSetup, BowlSetup.creator_id == User.id)
        .where(User.is_banned.is_(False))
        .group_by(User.id)
        .order_by(func.count(BowlSetup.id).desc(), func.lower(User.nickname).nullslast())
        .limit(safe_limit)
    )
    return [
        await _public_user_payload(db, user, viewer)
        for user, _setups_total in result.all()
    ]


@router.get("/recommended-users", response_model=list[PublicUserResponse])
async def get_recommended_users(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_limit = max(1, min(limit, 30))
    user_tobacco_ids = (
        select(BowlSetupTobacco.tobacco_id)
        .join(BowlSetup, BowlSetup.id == BowlSetupTobacco.bowl_setup_id)
        .where(BowlSetup.creator_id == current_user.id)
        .union(select(UserFavoriteTobacco.tobacco_id).where(UserFavoriteTobacco.user_id == current_user.id))
    )
    result = await db.execute(
        select(User, func.count(func.distinct(BowlSetupTobacco.tobacco_id)).label("matches"))
        .join(BowlSetup, BowlSetup.creator_id == User.id)
        .join(BowlSetupTobacco, BowlSetupTobacco.bowl_setup_id == BowlSetup.id)
        .where(
            User.id != current_user.id,
            User.is_banned.is_(False),
            BowlSetupTobacco.tobacco_id.in_(user_tobacco_ids),
        )
        .group_by(User.id)
        .order_by(func.count(func.distinct(BowlSetupTobacco.tobacco_id)).desc(), User.score.desc())
        .limit(safe_limit)
    )
    users = [user for user, _matches in result.all()]
    if not users:
        return await get_top_authors(safe_limit, db, current_user)
    return [await _public_user_payload(db, user, current_user) for user in users]


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


@router.get("/users/{user_id}/followers", response_model=list[PublicUserResponse])
async def read_public_user_followers(
    user_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_current_user),
):
    safe_limit = max(1, min(limit, 100))
    result = await db.execute(
        select(User)
        .join(UserFollow, UserFollow.follower_id == User.id)
        .where(UserFollow.followed_id == user_id, User.is_banned.is_(False))
        .order_by(UserFollow.created_at.desc())
        .limit(safe_limit)
    )
    return [await _public_user_payload(db, user, viewer) for user in result.scalars().all()]


@router.get("/users/{user_id}/following", response_model=list[PublicUserResponse])
async def read_public_user_following(
    user_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_current_user),
):
    safe_limit = max(1, min(limit, 100))
    result = await db.execute(
        select(User)
        .join(UserFollow, UserFollow.followed_id == User.id)
        .where(UserFollow.follower_id == user_id, User.is_banned.is_(False))
        .order_by(UserFollow.created_at.desc())
        .limit(safe_limit)
    )
    return [await _public_user_payload(db, user, viewer) for user in result.scalars().all()]


@router.get("/users/{user_id}/setups", response_model=BowlSetupPageResponse)
async def read_public_user_setups(
    user_id: uuid.UUID,
    limit: int = 24,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_current_user),
):
    user = await db.get(User, user_id)
    if not user or user.is_banned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return await crud.get_setups_page(
        db,
        creator_id=user_id,
        limit=limit,
        offset=offset,
        user_id=viewer.id if viewer else None,
    )


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
        db.add(Notification(
            user_id=user_id,
            actor_id=current_user.id,
            type="user_followed",
            title="New follower",
            body=f"{current_user.display_name} (/users/{current_user.id}) followed you.",
        ))
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


@router.get("/notifications/stream")
async def stream_notifications(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    current_user = await _get_user_from_token(token, db)

    async def events():
        last_id: uuid.UUID | None = None
        while True:
            result = await db.execute(
                select(Notification)
                .where(Notification.user_id == current_user.id)
                .order_by(Notification.created_at.desc())
                .limit(1)
            )
            notification = result.scalars().first()
            if notification and notification.id != last_id:
                last_id = notification.id
                payload = {
                    "id": str(notification.id),
                    "type": notification.type,
                    "title": notification.title,
                    "body": notification.body,
                    "actor_id": str(notification.actor_id) if notification.actor_id else None,
                    "bowl_setup_id": str(notification.bowl_setup_id) if notification.bowl_setup_id else None,
                    "created_at": notification.created_at.isoformat() if notification.created_at else None,
                }
                yield f"event: notification\ndata: {json.dumps(payload)}\n\n"
            else:
                yield "event: ping\ndata: {}\n\n"
            await asyncio.sleep(15)

    return StreamingResponse(events(), media_type="text/event-stream")


async def _collection_payload(db: AsyncSession, collection: SetupCollection) -> dict:
    result = await db.execute(
        select(SetupCollectionItem.bowl_setup_id).where(
            SetupCollectionItem.collection_id == collection.id
        )
    )
    setup_ids = list(result.scalars().all())
    return {
        "id": collection.id,
        "user_id": collection.user_id,
        "name": collection.name,
        "created_at": collection.created_at,
        "setup_ids": setup_ids,
        "items_count": len(setup_ids),
    }


@router.get("/collections", response_model=list[SetupCollectionResponse])
async def list_collections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SetupCollection)
        .where(SetupCollection.user_id == current_user.id)
        .order_by(SetupCollection.created_at.desc())
    )
    return [await _collection_payload(db, collection) for collection in result.scalars().all()]


@router.post("/collections", response_model=SetupCollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(
    item: SetupCollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = SetupCollection(user_id=current_user.id, name=item.name)
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return await _collection_payload(db, collection)


@router.post("/collections/{collection_id}/setups/{setup_id}", response_model=SetupCollectionResponse)
async def add_setup_to_collection(
    collection_id: uuid.UUID,
    setup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = await db.get(SetupCollection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await crud.get_setup_by_id(db, setup_id)
    existing = await db.scalar(
        select(SetupCollectionItem.id).where(
            SetupCollectionItem.collection_id == collection_id,
            SetupCollectionItem.bowl_setup_id == setup_id,
        )
    )
    if not existing:
        db.add(SetupCollectionItem(collection_id=collection_id, bowl_setup_id=setup_id))
        await db.commit()
    return await _collection_payload(db, collection)


@router.delete("/collections/{collection_id}/setups/{setup_id}", response_model=SetupCollectionResponse)
async def remove_setup_from_collection(
    collection_id: uuid.UUID,
    setup_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    collection = await db.get(SetupCollection, collection_id)
    if not collection or collection.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    item = await db.scalar(
        select(SetupCollectionItem).where(
            SetupCollectionItem.collection_id == collection_id,
            SetupCollectionItem.bowl_setup_id == setup_id,
        )
    )
    if item:
        await db.delete(item)
        await db.commit()
    return await _collection_payload(db, collection)


@router.get("/favorite-tobaccos", response_model=list[TobaccoResponse])
async def list_favorite_tobaccos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Tobacco)
        .join(UserFavoriteTobacco, UserFavoriteTobacco.tobacco_id == Tobacco.id)
        .where(UserFavoriteTobacco.user_id == current_user.id, Tobacco.deleted_at.is_(None))
        .order_by(func.lower(Tobacco.name))
    )
    tobaccos = result.scalars().all()
    for tobacco in tobaccos:
        setattr(tobacco, "is_favorite", True)
    return tobaccos


@router.post("/favorite-tobaccos/{tobacco_id}", response_model=list[TobaccoResponse])
async def add_favorite_tobacco(
    tobacco_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tobacco = await db.get(Tobacco, tobacco_id)
    if not tobacco or tobacco.deleted_at:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    existing = await db.scalar(
        select(UserFavoriteTobacco.id).where(
            UserFavoriteTobacco.user_id == current_user.id,
            UserFavoriteTobacco.tobacco_id == tobacco_id,
        )
    )
    if not existing:
        db.add(UserFavoriteTobacco(user_id=current_user.id, tobacco_id=tobacco_id))
        await db.commit()
    return await list_favorite_tobaccos(db, current_user)


@router.delete("/favorite-tobaccos/{tobacco_id}", response_model=list[TobaccoResponse])
async def remove_favorite_tobacco(
    tobacco_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    favorite = await db.scalar(
        select(UserFavoriteTobacco).where(
            UserFavoriteTobacco.user_id == current_user.id,
            UserFavoriteTobacco.tobacco_id == tobacco_id,
        )
    )
    if favorite:
        await db.delete(favorite)
        await db.commit()
    return await list_favorite_tobaccos(db, current_user)
