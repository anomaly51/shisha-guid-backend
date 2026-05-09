from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import shisha as crud
from app.models import shisha as models
from app.models.user import User
from app.schemas import shisha as schemas

router = APIRouter()


@router.post("/tobaccos", response_model=schemas.TobaccoResponse)
async def create_tobacco(
    item: schemas.TobaccoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.create_component(db, models.Tobacco, item, current_user.id)


@router.get("/tobaccos", response_model=list[schemas.TobaccoResponse])
async def get_tobaccos(db: AsyncSession = Depends(get_db)):
    return await crud.get_components(db, models.Tobacco)


# ... и так далее для Coals, Bowls, Kalouds (используя аналогичный паттерн)


@router.post("/bowl-setups", response_model=schemas.BowlSetupResponse)
async def create_bowl_setup(
    item: schemas.BowlSetupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.create_bowl_setup(db, item, current_user.id)


@router.get("/bowl-setups", response_model=list[schemas.BowlSetupResponse])
async def get_bowl_setups(db: AsyncSession = Depends(get_db)):
    return await crud.get_bowl_setups(db)
