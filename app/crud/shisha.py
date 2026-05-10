import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.storage import promote_file
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
    data = schema.model_dump()
    if "photo_urls" in data:
        data["photo_urls"] = [
            promote_file(url, model.__tablename__) for url in data["photo_urls"]
        ]
    item = model(**data, creator_id=user_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(db: AsyncSession, model, item_id: uuid.UUID, schema):
    item = await get_by_id(db, model, item_id)
    data = schema.model_dump(exclude_unset=True)
    if "photo_urls" in data:
        data["photo_urls"] = [
            promote_file(url, model.__tablename__) for url in data["photo_urls"]
        ]
    for key, value in data.items():
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
    if "photo_urls" in data:
        data["photo_urls"] = [
            promote_file(url, BowlSetup.__tablename__) for url in data["photo_urls"]
        ]
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
    if "photo_urls" in data:
        data["photo_urls"] = [
            promote_file(url, BowlSetup.__tablename__) for url in data["photo_urls"]
        ]
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
