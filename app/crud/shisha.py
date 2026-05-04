import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.shisha import BowlSetup, BowlSetupTobacco
from app.schemas.shisha import BowlSetupCreate

# --- УНИВЕРСАЛЬНЫЙ CRUD ДЛЯ БАЗОВЫХ КОМПОНЕНТОВ ---
# (Подходит для Tobacco, Coal, Kaloud, Bowl, CoalPlacement, BowlSetupType)


async def create_component(
    db: AsyncSession, model_class, schema_obj, creator_id: uuid.UUID
):
    # Превращаем Pydantic схему в словарь и распаковываем её в SQLAlchemy модель
    db_obj = model_class(**schema_obj.model_dump(), creator_id=creator_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_components(db: AsyncSession, model_class):
    result = await db.execute(select(model_class))
    return result.scalars().all()


# --- СПЕЦИФИЧНЫЙ CRUD ДЛЯ МИКСА (BOWL SETUP) ---


async def create_bowl_setup(
    db: AsyncSession, setup_in: BowlSetupCreate, creator_id: uuid.UUID
):
    # 1. Отделяем табаки от основных данных микса
    setup_data = setup_in.model_dump(exclude={"tobaccos"})
    db_setup = BowlSetup(**setup_data, creator_id=creator_id)

    db.add(db_setup)
    await db.flush()  # flush отправляет данные в БД, чтобы получить ID микса, но еще не делает окончательный commit

    # 2. Перебираем табаки и привязываем их к нашему новому миксу
    for tob_data in setup_in.tobaccos:
        db_setup_tobacco = BowlSetupTobacco(
            bowl_setup_id=db_setup.id,
            tobacco_id=tob_data.tobacco_id,
            percentage=tob_data.percentage,
        )
        db.add(db_setup_tobacco)

    await db.commit()  # Теперь окончательно сохраняем всё вместе (и микс, и табаки)

    # 3. Подгружаем связи (табаки), чтобы Pydantic схема ответа (Response) смогла их отобразить
    result = await db.execute(
        select(BowlSetup)
        .options(selectinload(BowlSetup.tobaccos))
        .where(BowlSetup.id == db_setup.id)
    )
    return result.scalars().first()


async def get_bowl_setups(db: AsyncSession):
    # Загружаем миксы сразу вместе с их табаками (чтобы не было проблемы N+1 запросов к БД)
    result = await db.execute(
        select(BowlSetup).options(selectinload(BowlSetup.tobaccos))
    )
    return result.scalars().all()
