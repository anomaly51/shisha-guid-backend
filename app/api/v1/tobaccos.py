import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import shisha as crud
from app.models.shisha import Tobacco
from app.models.user import User
from app.schemas.shisha import TobaccoCreate, TobaccoResponse

router = APIRouter()


@router.get("", response_model=list[TobaccoResponse])
async def get_tobaccos(db: AsyncSession = Depends(get_db)):
    return await crud.get_all(db, Tobacco)


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
    return await crud.update_item(db, Tobacco, item_id, item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tobacco(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item(db, Tobacco, item_id)
