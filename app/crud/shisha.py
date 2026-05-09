import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.shisha import BowlSetup, BowlSetupTobacco


async def get_all(db: AsyncSession, model):
    result = await db.execute(select(model))
    return result.scalars().all()


async def get_by_id(db: AsyncSession, model, item_id: uuid.UUID):
    result = await db.execute(select(model).where(model.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return item


async def create_item(db: AsyncSession, model, schema, user_id: uuid.UUID):
    item = model(**schema.model_dump(), creator_id=user_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(db: AsyncSession, model, item_id: uuid.UUID, schema):
    item = await get_by_id(db, model, item_id)
    for key, value in schema.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, model, item_id: uuid.UUID):
    item = await get_by_id(db, model, item_id)
    await db.delete(item)
    await db.commit()


async def get_all_setups(db: AsyncSession):
    result = await db.execute(
        select(BowlSetup).options(selectinload(BowlSetup.tobaccos))
    )
    return result.scalars().all()


async def get_setup_by_id(db: AsyncSession, item_id: uuid.UUID):
    result = await db.execute(
        select(BowlSetup)
        .options(selectinload(BowlSetup.tobaccos))
        .where(BowlSetup.id == item_id)
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return item


async def create_setup(db: AsyncSession, schema, user_id: uuid.UUID):
    data = schema.model_dump(exclude={"tobaccos"})
    setup = BowlSetup(**data, creator_id=user_id)
    db.add(setup)
    await db.flush()
    for tob in schema.tobaccos:
        db.add(
            BowlSetupTobacco(
                bowl_setup_id=setup.id,
                tobacco_id=tob.tobacco_id,
                percentage=tob.percentage,
            )
        )
    await db.commit()
    return await get_setup_by_id(db, setup.id)


async def update_setup(db: AsyncSession, item_id: uuid.UUID, schema):
    setup = await get_setup_by_id(db, item_id)
    data = schema.model_dump(exclude={"tobaccos"})
    for key, value in data.items():
        setattr(setup, key, value)
    for tob in setup.tobaccos:
        await db.delete(tob)
    await db.flush()
    for tob in schema.tobaccos:
        db.add(
            BowlSetupTobacco(
                bowl_setup_id=setup.id,
                tobacco_id=tob.tobacco_id,
                percentage=tob.percentage,
            )
        )
    await db.commit()
    return await get_setup_by_id(db, setup.id)
