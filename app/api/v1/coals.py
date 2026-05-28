import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import catalog_cache
from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import base as crud
from app.crud import catalog
from app.models.shisha import Coal, Kaloud
from app.models.user import User
from app.schemas.shisha import (
    CoalCreate,
    CoalPageResponse,
    CoalResponse,
    KaloudCreate,
    KaloudResponse,
)

router = APIRouter()


@router.get("/coals", response_model=list[CoalResponse] | CoalPageResponse)
async def get_coals(
    search: str | None = Query(default=None, min_length=1),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    if limit is not None:
        return await catalog.get_coals_page(
            db,
            search=search,
            limit=limit,
            offset=offset,
        )
    return await crud.get_all(db, Coal, limit=500, offset=offset)


@router.post("/coals", response_model=CoalResponse, status_code=status.HTTP_201_CREATED)
async def create_coal(
    item: CoalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    created = await crud.create_item(db, Coal, item, user.id)
    return created


@router.get("/coals/{item_id}", response_model=CoalResponse)
async def get_coal(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await crud.get_by_id(db, Coal, item_id)


@router.patch("/coals/{item_id}", response_model=CoalResponse)
async def update_coal(
    item_id: uuid.UUID,
    item: CoalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    updated = await crud.update_item_for_user(db, Coal, item_id, item, user)
    return updated


@router.delete("/coals/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coal(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item_for_user(db, Coal, item_id, user)


@router.get("/kalouds", response_model=list[KaloudResponse])
async def get_kalouds(
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_cache.get_or_set(
        f"kalouds:{limit}:{offset}",
        lambda: crud.get_all(db, Kaloud, limit=limit, offset=offset),
    )


@router.post(
    "/kalouds", response_model=KaloudResponse, status_code=status.HTTP_201_CREATED
)
async def create_kaloud(
    item: KaloudCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    created = await crud.create_item(db, Kaloud, item, user.id)
    await catalog_cache.clear_prefix("kalouds:")
    return created


@router.get("/kalouds/{item_id}", response_model=KaloudResponse)
async def get_kaloud(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await crud.get_by_id(db, Kaloud, item_id)


@router.patch("/kalouds/{item_id}", response_model=KaloudResponse)
async def update_kaloud(
    item_id: uuid.UUID,
    item: KaloudCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    updated = await crud.update_item_for_user(db, Kaloud, item_id, item, user)
    await catalog_cache.clear_prefix("kalouds:")
    return updated


@router.delete("/kalouds/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kaloud(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item_for_user(db, Kaloud, item_id, user)
    await catalog_cache.clear_prefix("kalouds:")
