import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_optional_current_user
from app.crud import base as crud
from app.crud import catalog
from app.models.shisha import BowlSetup, BowlSetupTobacco, Tobacco
from app.models.user import User, UserFavoriteTobacco
from app.schemas.shisha import TobaccoCreate, TobaccoPageResponse, TobaccoResponse
from app.schemas.user import PublicUserResponse
from app.api.v1.profile import _public_user_payload

router = APIRouter()


@router.get("", response_model=list[TobaccoResponse] | TobaccoPageResponse)
async def get_tobaccos(
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    strength: Literal["all", "light", "medium", "strong", "heavy"] = "all",
    search: str | None = Query(default=None, min_length=1),
    brand: str | None = Query(default=None, min_length=1),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    if limit is not None:
        page = await catalog.get_tobaccos_page(
            db,
            min_price=min_price,
            max_price=max_price,
            strength=strength,
            search=search,
            brand=brand,
            limit=limit,
            offset=offset,
        )
        await _decorate_favorite_tobaccos(db, page["items"], user.id if user else None)
        return page
    tobaccos = await catalog.get_filtered_tobaccos(
        db,
        min_price=min_price,
        max_price=max_price,
        strength=strength,
        search=search,
        brand=brand,
    )
    await _decorate_favorite_tobaccos(db, tobaccos, user.id if user else None)
    return tobaccos


async def _decorate_favorite_tobaccos(db: AsyncSession, tobaccos: list[Tobacco], user_id: uuid.UUID | None):
    if not user_id or not tobaccos:
        return
    result = await db.execute(
        select(UserFavoriteTobacco.tobacco_id).where(
            UserFavoriteTobacco.user_id == user_id,
            UserFavoriteTobacco.tobacco_id.in_([tobacco.id for tobacco in tobaccos]),
        )
    )
    favorite_ids = set(result.scalars().all())
    for tobacco in tobaccos:
        setattr(tobacco, "is_favorite", tobacco.id in favorite_ids)


@router.post("", response_model=TobaccoResponse, status_code=status.HTTP_201_CREATED)
async def create_tobacco(
    item: TobaccoCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_item(db, Tobacco, item, user.id)


@router.get("/{item_id}", response_model=TobaccoResponse)
async def get_tobacco(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    tobacco = await crud.get_by_id(db, Tobacco, item_id)
    await _decorate_favorite_tobaccos(db, [tobacco], user.id if user else None)
    return tobacco


@router.get("/{item_id}/users", response_model=list[PublicUserResponse])
async def get_tobacco_users(
    item_id: uuid.UUID,
    limit: int = Query(default=12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_current_user),
):
    await crud.get_by_id(db, Tobacco, item_id)
    result = await db.execute(
        select(User, func.count(distinct(BowlSetup.id)).label("setups_total"))
        .join(BowlSetup, BowlSetup.creator_id == User.id)
        .join(BowlSetupTobacco, BowlSetupTobacco.bowl_setup_id == BowlSetup.id)
        .where(BowlSetupTobacco.tobacco_id == item_id, User.is_banned.is_(False))
        .group_by(User.id)
        .order_by(func.count(distinct(BowlSetup.id)).desc(), User.score.desc())
        .limit(limit)
    )
    return [await _public_user_payload(db, user, viewer) for user, _count in result.all()]


@router.patch("/{item_id}", response_model=TobaccoResponse)
async def update_tobacco(
    item_id: uuid.UUID,
    item: TobaccoCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.update_item_for_user(db, Tobacco, item_id, item, user)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tobacco(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item_for_user(db, Tobacco, item_id, user)
