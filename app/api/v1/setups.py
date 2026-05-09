import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import shisha as crud
from app.models.shisha import BowlSetup, BowlSetupType, CoalPlacement
from app.models.user import User
from app.schemas.shisha import (
    BowlSetupCreate,
    BowlSetupResponse,
    BowlSetupTypeCreate,
    BowlSetupTypeResponse,
    CoalPlacementCreate,
    CoalPlacementResponse,
)

router = APIRouter()


@router.get("/coal-placements", response_model=list[CoalPlacementResponse])
async def get_coal_placements(db: AsyncSession = Depends(get_db)):
    return await crud.get_all(db, CoalPlacement)


@router.post(
    "/coal-placements",
    response_model=CoalPlacementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_coal_placement(
    item: CoalPlacementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_item(db, CoalPlacement, item, user.id)


@router.get("/coal-placements/{item_id}", response_model=CoalPlacementResponse)
async def get_coal_placement(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await crud.get_by_id(db, CoalPlacement, item_id)


@router.patch("/coal-placements/{item_id}", response_model=CoalPlacementResponse)
async def update_coal_placement(
    item_id: uuid.UUID,
    item: CoalPlacementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.update_item(db, CoalPlacement, item_id, item)


@router.delete("/coal-placements/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coal_placement(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item(db, CoalPlacement, item_id)


@router.get("/bowl-setup-types", response_model=list[BowlSetupTypeResponse])
async def get_bowl_setup_types(db: AsyncSession = Depends(get_db)):
    return await crud.get_all(db, BowlSetupType)


@router.post(
    "/bowl-setup-types",
    response_model=BowlSetupTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bowl_setup_type(
    item: BowlSetupTypeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_item(db, BowlSetupType, item, user.id)


@router.get("/bowl-setup-types/{item_id}", response_model=BowlSetupTypeResponse)
async def get_bowl_setup_type(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await crud.get_by_id(db, BowlSetupType, item_id)


@router.patch("/bowl-setup-types/{item_id}", response_model=BowlSetupTypeResponse)
async def update_bowl_setup_type(
    item_id: uuid.UUID,
    item: BowlSetupTypeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.update_item(db, BowlSetupType, item_id, item)


@router.delete("/bowl-setup-types/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bowl_setup_type(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item(db, BowlSetupType, item_id)


@router.get("/bowl-setups", response_model=list[BowlSetupResponse])
async def get_bowl_setups(db: AsyncSession = Depends(get_db)):
    return await crud.get_all_setups(db)


@router.post(
    "/bowl-setups",
    response_model=BowlSetupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bowl_setup(
    item: BowlSetupCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_setup(db, item, user.id)


@router.get("/bowl-setups/{item_id}", response_model=BowlSetupResponse)
async def get_bowl_setup(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await crud.get_setup_by_id(db, item_id)


@router.patch("/bowl-setups/{item_id}", response_model=BowlSetupResponse)
async def update_bowl_setup(
    item_id: uuid.UUID,
    item: BowlSetupCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.update_setup(db, item_id, item)


@router.delete("/bowl-setups/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bowl_setup(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item(db, BowlSetup, item_id)
