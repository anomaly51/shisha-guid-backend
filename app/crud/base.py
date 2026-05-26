import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.storage import promote_file


async def get_all(db: AsyncSession, model):
    result = await db.execute(select(model))
    return result.scalars().all()


async def get_by_id(db: AsyncSession, model, item_id: uuid.UUID):
    result = await db.execute(select(model).where(model.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return item


def _promote_photo_urls(model, data: dict) -> dict:
    if "photo_urls" in data:
        data["photo_urls"] = [
            promote_file(url, model.__tablename__) for url in data["photo_urls"]
        ]
    return data


async def create_item(db: AsyncSession, model, schema, user_id: uuid.UUID):
    data = _promote_photo_urls(model, schema.model_dump())
    item = model(**data, creator_id=user_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(db: AsyncSession, model, item_id: uuid.UUID, schema):
    item = await get_by_id(db, model, item_id)
    data = _promote_photo_urls(model, schema.model_dump(exclude_unset=True))
    for key, value in data.items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item_for_user(
    db: AsyncSession,
    model,
    item_id: uuid.UUID,
    schema,
    user,
):
    item = await get_by_id(db, model, item_id)
    if item.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    data = _promote_photo_urls(model, schema.model_dump(exclude_unset=True))
    for key, value in data.items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, model, item_id: uuid.UUID):
    item = await get_by_id(db, model, item_id)
    await db.delete(item)
    await db.commit()


async def delete_item_for_user(db: AsyncSession, model, item_id: uuid.UUID, user):
    item = await get_by_id(db, model, item_id)
    if item.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await db.delete(item)
    await db.commit()
