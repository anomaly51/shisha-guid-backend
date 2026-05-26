import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import shisha as crud
from app.models.shisha import Tobacco
from app.models.user import User
from app.schemas.shisha import TobaccoCreate, TobaccoPageResponse, TobaccoResponse

router = APIRouter()


@router.get("", response_model=list[TobaccoResponse] | TobaccoPageResponse)
async def get_tobaccos(
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    strength: Literal["all", "light", "medium", "strong", "heavy"] = "all",
    search: str | None = Query(default=None, min_length=1),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    if limit is not None:
        return await crud.get_tobaccos_page(
            db,
            min_price=min_price,
            max_price=max_price,
            strength=strength,
            search=search,
            limit=limit,
            offset=offset,
        )
    return await crud.get_filtered_tobaccos(
        db,
        min_price=min_price,
        max_price=max_price,
        strength=strength,
        search=search,
    )


@router.post("", response_model=TobaccoResponse, status_code=status.HTTP_201_CREATED)
async def create_tobacco(
    item: TobaccoCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_item(db, Tobacco, item, user.id)


@router.get("/{item_id}", response_model=TobaccoResponse)
async def get_tobacco(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await crud.get_by_id(db, Tobacco, item_id)


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
