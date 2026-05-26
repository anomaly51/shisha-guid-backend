import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import base as crud
from app.models.shisha import Bowl
from app.models.user import User
from app.schemas.shisha import BowlCreate, BowlResponse

router = APIRouter()


@router.get("", response_model=list[BowlResponse])
async def get_bowls(db: AsyncSession = Depends(get_db)):
    return await crud.get_all(db, Bowl)


@router.post("", response_model=BowlResponse, status_code=status.HTTP_201_CREATED)
async def create_bowl(
    item: BowlCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_item(db, Bowl, item, user.id)


@router.get("/{item_id}", response_model=BowlResponse)
async def get_bowl(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await crud.get_by_id(db, Bowl, item_id)


@router.patch("/{item_id}", response_model=BowlResponse)
async def update_bowl(
    item_id: uuid.UUID,
    item: BowlCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.update_item_for_user(db, Bowl, item_id, item, user)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bowl(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item_for_user(db, Bowl, item_id, user)
