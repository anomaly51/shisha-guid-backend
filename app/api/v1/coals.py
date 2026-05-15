import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import shisha as crud
from app.models.shisha import Coal, Kaloud
from app.models.user import User
from app.schemas.shisha import CoalCreate, CoalResponse, KaloudCreate, KaloudResponse

router = APIRouter()


@router.get("/coals", response_model=list[CoalResponse])
async def get_coals(db: AsyncSession = Depends(get_db)):
    return await crud.get_all(db, Coal)


@router.post("/coals", response_model=CoalResponse, status_code=status.HTTP_201_CREATED)
async def create_coal(
    item: CoalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_item(db, Coal, item, user.id)


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
    return await crud.update_item_for_user(db, Coal, item_id, item, user)


@router.delete("/coals/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coal(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item_for_user(db, Coal, item_id, user)


@router.get("/kalouds", response_model=list[KaloudResponse])
async def get_kalouds(db: AsyncSession = Depends(get_db)):
    return await crud.get_all(db, Kaloud)


@router.post(
    "/kalouds", response_model=KaloudResponse, status_code=status.HTTP_201_CREATED
)
async def create_kaloud(
    item: KaloudCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_item(db, Kaloud, item, user.id)


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
    return await crud.update_item_for_user(db, Kaloud, item_id, item, user)


@router.delete("/kalouds/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kaloud(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item_for_user(db, Kaloud, item_id, user)
