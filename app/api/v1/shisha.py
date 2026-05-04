from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.crud import shisha as crud

# Импортируем наши модели, схемы и CRUD как модули для краткости
from app.models import shisha as models
from app.models.user import User
from app.schemas import shisha as schemas

router = APIRouter()


# --- TOBACCO ---
@router.post("/tobaccos", response_model=schemas.TobaccoResponse)
async def create_tobacco(
    item: schemas.TobaccoCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # Защита: только для авторизованных
):
    return await crud.create_component(db, models.Tobacco, item, current_user.id)


@router.get("/tobaccos", response_model=list[schemas.TobaccoResponse])
async def get_tobaccos(db: AsyncSession = Depends(get_db)):
    return await crud.get_components(db, models.Tobacco)


# --- COAL ---
@router.post("/coals", response_model=schemas.CoalResponse)
async def create_coal(
    item: schemas.CoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.create_component(db, models.Coal, item, current_user.id)


@router.get("/coals", response_model=list[schemas.CoalResponse])
async def get_coals(db: AsyncSession = Depends(get_db)):
    return await crud.get_components(db, models.Coal)


# --- KALOUD ---
@router.post("/kalouds", response_model=schemas.KaloudResponse)
async def create_kaloud(
    item: schemas.KaloudCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.create_component(db, models.Kaloud, item, current_user.id)


@router.get("/kalouds", response_model=list[schemas.KaloudResponse])
async def get_kalouds(db: AsyncSession = Depends(get_db)):
    return await crud.get_components(db, models.Kaloud)


# --- BOWL ---
@router.post("/bowls", response_model=schemas.BowlResponse)
async def create_bowl(
    item: schemas.BowlCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.create_component(db, models.Bowl, item, current_user.id)


@router.get("/bowls", response_model=list[schemas.BowlResponse])
async def get_bowls(db: AsyncSession = Depends(get_db)):
    return await crud.get_components(db, models.Bowl)


# --- COAL PLACEMENT ---
@router.post("/coal-placements", response_model=schemas.CoalPlacementResponse)
async def create_coal_placement(
    item: schemas.CoalPlacementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.create_component(db, models.CoalPlacement, item, current_user.id)


@router.get("/coal-placements", response_model=list[schemas.CoalPlacementResponse])
async def get_coal_placements(db: AsyncSession = Depends(get_db)):
    return await crud.get_components(db, models.CoalPlacement)


# --- BOWL SETUP TYPE ---
@router.post("/bowl-setup-types", response_model=schemas.BowlSetupTypeResponse)
async def create_bowl_setup_type(
    item: schemas.BowlSetupTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud.create_component(db, models.BowlSetupType, item, current_user.id)


@router.get("/bowl-setup-types", response_model=list[schemas.BowlSetupTypeResponse])
async def get_bowl_setup_types(db: AsyncSession = Depends(get_db)):
    return await crud.get_components(db, models.BowlSetupType)


# --- BOWL SETUP (ГЛАВНЫЙ МИКС) ---
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
