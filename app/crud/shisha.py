import uuid
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import distinct, func, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.storage import promote_file
from app.core.email import send_email
from app.models.shisha import (
    BowlSetup,
    BowlSetupReview,
    BowlSetupTobacco,
    BowlSetupVersion,
    BowlSetupView,
    Coal,
    Tobacco,
)
from app.models.user import Notification, SetupBookmark, User, UserFollow


VIEW_INTERVAL = timedelta(minutes=30)


STRENGTH_RANGES = {
    "light": (0, 4.49),
    "medium": (4.5, 6.49),
    "strong": (6.5, 7.99),
    "heavy": (8, 10),
}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(maximum, max(minimum, value))


def get_tobacco_strength(tobacco) -> float:
    explicit_value = next(
        (
            value
            for value in (
                getattr(tobacco, "strength", None),
                getattr(tobacco, "heaviness", None),
                getattr(tobacco, "nicotine_strength", None),
                getattr(tobacco, "nicotine", None),
            )
            if value is not None
        ),
        None,
    )
    if explicit_value is not None:
        try:
            numeric = float(explicit_value)
            if numeric >= 0:
                return _clamp(numeric, 0, 10)
        except (TypeError, ValueError):
            pass

    text = f"{getattr(tobacco, 'name', '') or ''} {getattr(tobacco, 'description', '') or ''}".lower()
    score = 5

    if "darkside" in text:
        score += 3
    if "blackburn" in text or "strong" in text or "креп" in text:
        score += 2
    if "musthave" in text or "sebero" in text:
        score += 1
    if "duft" in text or "mango" in text or "слив" in text or "мягк" in text:
        score -= 1
    if "element" in text or "banana" in text or "milk" in text or "легк" in text:
        score -= 2

    return _clamp(score, 0, 10)


def _matches_strength(value: float, strength: str | None) -> bool:
    if not strength or strength == "all":
        return True
    strength_range = STRENGTH_RANGES.get(strength)
    if not strength_range:
        return True
    return strength_range[0] <= value <= strength_range[1]


def get_setup_heaviness(setup: BowlSetup) -> float:
    if setup.heaviness_score is not None:
        return _clamp(float(setup.heaviness_score), 0, 10)

    mix = setup.tobaccos or []
    if not mix:
        return 5

    total = sum(int(item.percentage or 0) for item in mix) or 100
    value = 0.0

    for item in mix:
        value += get_tobacco_strength(item.tobacco) * (int(item.percentage or 0) / total)

    return _clamp(value, 0, 10)


def _setup_rating(setup: BowlSetup) -> float:
    if setup.rating_average is not None:
        return round(float(setup.rating_average), 1)
    ratings = [review.rating for review in setup.reviews or []]
    return round(sum(ratings) / len(ratings), 1) if ratings else 0


def _snapshot_setup(setup: BowlSetup) -> dict:
    return {
        "name": setup.name,
        "description": setup.description,
        "photo_urls": setup.photo_urls or [],
        "bowl_id": str(setup.bowl_id),
        "kaloud_id": str(setup.kaloud_id),
        "coal_id": str(setup.coal_id),
        "coal_placement_id": str(setup.coal_placement_id),
        "bowl_setup_type_id": str(setup.bowl_setup_type_id),
        "tobaccos": [
            {"tobacco_id": str(item.tobacco_id), "percentage": item.percentage}
            for item in setup.tobaccos or []
        ],
    }


async def _decorate_setups(
    db: AsyncSession,
    setups: list[BowlSetup],
    user_id: uuid.UUID | None = None,
) -> list[BowlSetup]:
    if not setups:
        return setups

    creator_ids = {setup.creator_id for setup in setups}
    counts_result = await db.execute(
        select(BowlSetup.creator_id, func.count(BowlSetup.id))
        .where(BowlSetup.creator_id.in_(creator_ids))
        .group_by(BowlSetup.creator_id)
    )
    setup_counts = {creator_id: int(count) for creator_id, count in counts_result.all()}

    bookmarked_ids: set[uuid.UUID] = set()
    if user_id:
        bookmark_result = await db.execute(
            select(SetupBookmark.bowl_setup_id).where(
                SetupBookmark.user_id == user_id,
                SetupBookmark.bowl_setup_id.in_([setup.id for setup in setups]),
            )
        )
        bookmarked_ids = set(bookmark_result.scalars().all())

    for setup in setups:
        if setup.creator:
            setattr(setup.creator, "setups_count", setup_counts.get(setup.creator_id, 0))
        setattr(setup, "is_bookmarked", setup.id in bookmarked_ids)
    return setups


async def _calculate_heaviness_score(db: AsyncSession, tobaccos) -> float:
    tobacco_ids = [item.tobacco_id for item in tobaccos]
    if not tobacco_ids:
        return 5

    result = await db.execute(select(Tobacco).where(Tobacco.id.in_(tobacco_ids)))
    tobacco_by_id = {tobacco.id: tobacco for tobacco in result.scalars().all()}
    total = sum(int(item.percentage or 0) for item in tobaccos) or 100
    value = 0.0

    for item in tobaccos:
        tobacco = tobacco_by_id.get(item.tobacco_id)
        if tobacco:
            value += get_tobacco_strength(tobacco) * (int(item.percentage or 0) / total)

    return round(_clamp(value or 5, 0, 10), 1)


async def _refresh_setup_rating(db: AsyncSession, setup_id: uuid.UUID) -> None:
    result = await db.execute(
        select(
            func.coalesce(func.avg(BowlSetupReview.rating), 0),
            func.count(BowlSetupReview.id),
        ).where(BowlSetupReview.bowl_setup_id == setup_id)
    )
    average, count = result.one()
    setup = await get_setup_by_id(db, setup_id)
    setup.rating_average = round(float(average or 0), 1)
    setup.rating_count = int(count or 0)


async def get_all(db: AsyncSession, model, limit: int = 500, offset: int = 0):
    query = select(model)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    result = await db.execute(
        query.order_by(model.created_at.desc()).offset(max(0, offset)).limit(max(1, min(limit, 500)))
    )
    return result.scalars().all()


async def get_filtered_tobaccos(
    db: AsyncSession,
    min_price: int | None = None,
    max_price: int | None = None,
    strength: str | None = None,
    search: str | None = None,
):
    query = select(Tobacco).where(Tobacco.deleted_at.is_(None))
    if min_price is not None:
        query = query.where(Tobacco.price >= min_price)
    if max_price is not None:
        query = query.where(Tobacco.price <= max_price)
    if search:
        normalized = f"%{search.strip()}%"
        query = query.where(
            Tobacco.name.ilike(normalized) | Tobacco.description.ilike(normalized)
        )

    result = await db.execute(query.order_by(func.lower(Tobacco.name)))
    tobaccos = result.scalars().all()
    return [
        tobacco
        for tobacco in tobaccos
        if _matches_strength(get_tobacco_strength(tobacco), strength)
    ]


async def get_tobaccos_page(
    db: AsyncSession,
    min_price: int | None = None,
    max_price: int | None = None,
    strength: str | None = None,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    limit = max(1, min(limit or 24, 100))
    offset = max(0, offset)
    tobaccos = await get_filtered_tobaccos(
        db,
        min_price=min_price,
        max_price=max_price,
        strength=strength,
        search=search,
    )
    total = len(tobaccos)
    items = tobaccos[offset:offset + limit]
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


async def get_coals_page(
    db: AsyncSession,
    search: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    limit = max(1, min(limit or 24, 100))
    offset = max(0, offset)
    query = select(Coal).where(Coal.deleted_at.is_(None))

    if search:
        normalized = f"%{search.strip()}%"
        query = query.where(
            Coal.name.ilike(normalized) | Coal.description.ilike(normalized)
        )

    total_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total_result.scalar_one()
    result = await db.execute(
        query.order_by(func.lower(Coal.name)).offset(offset).limit(limit)
    )
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


async def get_by_id(db: AsyncSession, model, item_id: uuid.UUID):
    query = select(model).where(model.id == item_id)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    result = await db.execute(query)
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return item


async def create_item(db: AsyncSession, model, schema, user_id: uuid.UUID):
    data = schema.model_dump()
    if "photo_urls" in data:
        data["photo_urls"] = [
            promote_file(url, model.__tablename__, str(user_id))
            for url in data["photo_urls"]
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
    data = schema.model_dump(exclude_unset=True)
    if "photo_urls" in data:
        data["photo_urls"] = [
            promote_file(url, model.__tablename__, str(user.id))
            for url in data["photo_urls"]
        ]
    for key, value in data.items():
        setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return item


async def delete_item(db: AsyncSession, model, item_id: uuid.UUID):
    item = await get_by_id(db, model, item_id)
    if hasattr(item, "deleted_at"):
        item.deleted_at = func.now()
        await db.commit()
        return
    await db.delete(item)
    await db.commit()


async def delete_item_for_user(db: AsyncSession, model, item_id: uuid.UUID, user):
    item = await get_by_id(db, model, item_id)
    if item.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if hasattr(item, "deleted_at"):
        item.deleted_at = func.now()
        await db.commit()
        return
    await db.delete(item)
    await db.commit()


async def get_all_setups(
    db: AsyncSession,
    tobacco_ids: list[uuid.UUID] | None = None,
    strength: str | None = None,
    sort: str = "newest",
    search: str | None = None,
    creator_id: uuid.UUID | None = None,
    bookmarked_by: uuid.UUID | None = None,
    followed_by: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
):
    page = await get_setups_page(
        db,
        tobacco_ids,
        strength,
        sort,
        search=search,
        creator_id=creator_id,
        bookmarked_by=bookmarked_by,
        followed_by=followed_by,
        user_id=user_id,
    )
    return page["items"]


async def get_setups_page(
    db: AsyncSession,
    tobacco_ids: list[uuid.UUID] | None = None,
    strength: str | None = None,
    sort: str = "newest",
    limit: int | None = None,
    offset: int = 0,
    search: str | None = None,
    creator_id: uuid.UUID | None = None,
    bookmarked_by: uuid.UUID | None = None,
    followed_by: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
):
    limit = max(1, min(limit or 50, 50))
    offset = max(0, offset)
    selected_tobacco_ids = list(dict.fromkeys(tobacco_ids or []))

    query = select(BowlSetup).options(
        selectinload(BowlSetup.tobaccos).selectinload(BowlSetupTobacco.tobacco),
        selectinload(BowlSetup.creator),
    )

    if selected_tobacco_ids:
        matching_setup_ids = (
            select(BowlSetupTobacco.bowl_setup_id)
            .where(BowlSetupTobacco.tobacco_id.in_(selected_tobacco_ids))
            .group_by(BowlSetupTobacco.bowl_setup_id)
            .having(func.count(distinct(BowlSetupTobacco.tobacco_id)) == len(selected_tobacco_ids))
        )
        query = query.where(BowlSetup.id.in_(matching_setup_ids))
    if search:
        normalized = f"%{search.strip()}%"
        query = query.where(
            BowlSetup.name.ilike(normalized) | BowlSetup.description.ilike(normalized)
        )
    if creator_id:
        query = query.where(BowlSetup.creator_id == creator_id)
    if bookmarked_by:
        bookmarked_setup_ids = select(SetupBookmark.bowl_setup_id).where(
            SetupBookmark.user_id == bookmarked_by
        )
        query = query.where(BowlSetup.id.in_(bookmarked_setup_ids))
    if followed_by:
        followed_creator_ids = select(UserFollow.followed_id).where(
            UserFollow.follower_id == followed_by
        )
        query = query.where(BowlSetup.creator_id.in_(followed_creator_ids))

    if strength and strength != "all":
        strength_range = STRENGTH_RANGES.get(strength)
        if strength_range:
            query = query.where(
                BowlSetup.heaviness_score >= strength_range[0],
                BowlSetup.heaviness_score <= strength_range[1],
            )

    can_page_in_db = sort in {"newest", "views", "name", "rating", "strengthDesc", "strengthAsc"}

    if can_page_in_db:
        total_result = await db.execute(
            select(func.count()).select_from(query.order_by(None).subquery())
        )
        total = total_result.scalar_one()

        if sort == "views":
            query = query.order_by(BowlSetup.views_count.desc(), BowlSetup.created_at.desc())
        elif sort == "rating":
            query = query.order_by(BowlSetup.rating_average.desc(), BowlSetup.created_at.desc())
        elif sort == "strengthDesc":
            query = query.order_by(BowlSetup.heaviness_score.desc().nullslast(), BowlSetup.created_at.desc())
        elif sort == "strengthAsc":
            query = query.order_by(BowlSetup.heaviness_score.asc().nullslast(), BowlSetup.created_at.desc())
        elif sort == "name":
            query = query.order_by(func.lower(BowlSetup.name), BowlSetup.created_at.desc())
        else:
            query = query.order_by(BowlSetup.created_at.desc())

        result = await db.execute(query.offset(offset).limit(limit))
        items = result.scalars().all()
        await _decorate_setups(db, items, user_id)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    result = await db.execute(
        query
    )
    setups = result.scalars().all()

    setups = [
        setup
        for setup in setups
        if _matches_strength(get_setup_heaviness(setup), strength)
    ]

    if sort == "rating":
        setups = sorted(setups, key=_setup_rating, reverse=True)
    elif sort == "views":
        setups = sorted(setups, key=lambda setup: setup.views_count or 0, reverse=True)
    elif sort == "strengthDesc":
        setups = sorted(setups, key=get_setup_heaviness, reverse=True)
    elif sort == "strengthAsc":
        setups = sorted(setups, key=get_setup_heaviness)
    elif sort == "name":
        setups = sorted(setups, key=lambda setup: (setup.name or "").lower())
    else:
        setups = sorted(setups, key=lambda setup: setup.created_at, reverse=True)

    total = len(setups)
    items = setups[offset:offset + limit]
    await _decorate_setups(db, items, user_id)
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


async def get_setup_by_id(
    db: AsyncSession,
    item_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
):
    result = await db.execute(
        select(BowlSetup)
        .options(
            selectinload(BowlSetup.tobaccos).selectinload(BowlSetupTobacco.tobacco),
            selectinload(BowlSetup.creator),
        )
        .where(BowlSetup.id == item_id)
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _decorate_setups(db, [item], user_id)
    return item


async def record_setup_view(
    db: AsyncSession,
    setup: BowlSetup,
    ip_address: str | None,
    user_id: uuid.UUID | None = None,
) -> BowlSetup:
    if user_id and setup.creator_id == user_id:
        return setup
    if not ip_address:
        return setup

    normalized_ip = ip_address[:64]
    now_result = await db.execute(select(func.now()))
    now = now_result.scalar_one()
    cutoff = now - VIEW_INTERVAL

    result = await db.execute(
        select(BowlSetupView).where(
            BowlSetupView.bowl_setup_id == setup.id,
            BowlSetupView.ip_address == normalized_ip,
        )
    )
    view = result.scalars().first()

    should_count = view is None or view.last_viewed_at <= cutoff
    if not should_count:
        return setup

    counted = False

    if view is None:
        statement = (
            insert(BowlSetupView)
            .values(bowl_setup_id=setup.id, ip_address=normalized_ip)
            .on_conflict_do_nothing(
                index_elements=["bowl_setup_id", "ip_address"],
            )
            .returning(BowlSetupView.id)
        )
        try:
            insert_result = await db.execute(statement)
            counted = insert_result.scalar_one_or_none() is not None
        except IntegrityError:
            await db.rollback()
            counted = False
    else:
        update_result = await db.execute(
            update(BowlSetupView)
            .where(
                BowlSetupView.id == view.id,
                BowlSetupView.last_viewed_at <= cutoff,
            )
            .values(last_viewed_at=now)
            .returning(BowlSetupView.id)
        )
        counted = update_result.scalar_one_or_none() is not None

    if not counted:
        return setup

    await db.execute(
        update(BowlSetup)
        .where(BowlSetup.id == setup.id)
        .values(views_count=BowlSetup.views_count + 1)
    )
    await db.commit()
    return await get_setup_by_id(db, setup.id)


async def create_setup(db: AsyncSession, schema, user_id: uuid.UUID):
    data = schema.model_dump(exclude={"tobaccos"})
    data["photo_urls"] = [
        promote_file(url, "bowl_setups", str(user_id)) for url in data.get("photo_urls", [])
    ]
    data["heaviness_score"] = await _calculate_heaviness_score(db, schema.tobaccos)
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
    db.add(BowlSetupVersion(
        bowl_setup_id=setup.id,
        version=setup.version,
        snapshot=_snapshot_setup(setup),
    ))
    data = schema.model_dump(exclude={"tobaccos"})
    data["photo_urls"] = [
        promote_file(url, "bowl_setups", str(setup.creator_id)) for url in data.get("photo_urls", [])
    ]
    data["heaviness_score"] = await _calculate_heaviness_score(db, schema.tobaccos)
    for key, value in data.items():
        setattr(setup, key, value)
    setup.version = (setup.version or 1) + 1
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


async def update_setup_for_user(db: AsyncSession, item_id: uuid.UUID, schema, user):
    setup = await get_setup_by_id(db, item_id)
    if setup.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    db.add(BowlSetupVersion(
        bowl_setup_id=setup.id,
        version=setup.version,
        snapshot=_snapshot_setup(setup),
    ))
    data = schema.model_dump(exclude={"tobaccos"})
    data["photo_urls"] = [
        promote_file(url, "bowl_setups", str(setup.creator_id)) for url in data.get("photo_urls", [])
    ]
    data["heaviness_score"] = await _calculate_heaviness_score(db, schema.tobaccos)
    for key, value in data.items():
        setattr(setup, key, value)
    setup.version = (setup.version or 1) + 1
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


async def get_setup_reviews(db: AsyncSession, setup_id: uuid.UUID):
    await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(BowlSetupReview)
        .options(selectinload(BowlSetupReview.creator))
        .where(BowlSetupReview.bowl_setup_id == setup_id)
        .order_by(BowlSetupReview.created_at.desc())
    )
    return result.scalars().all()


async def create_setup_review(db: AsyncSession, setup_id: uuid.UUID, schema, user):
    setup = await get_setup_by_id(db, setup_id)
    if setup.creator_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot review your own setup",
        )
    existing = await db.execute(
        select(BowlSetupReview).where(
            BowlSetupReview.bowl_setup_id == setup_id,
            BowlSetupReview.creator_id == user.id,
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already reviewed this setup",
        )

    review = BowlSetupReview(
        bowl_setup_id=setup_id,
        creator_id=user.id,
        **schema.model_dump(),
    )
    db.add(review)
    if setup.creator_id != user.id:
        notification = Notification(
            user_id=setup.creator_id,
            actor_id=user.id,
            bowl_setup_id=setup.id,
            type="setup_review",
            title="New setup review",
            body=f"{user.display_name} reviewed your setup {setup.name}.",
        )
        db.add(notification)
        owner = await db.get(User, setup.creator_id)
        if owner:
            send_email(
                owner.email,
                "New review on your ShishaGuid setup",
                f"{user.display_name} reviewed your setup \"{setup.name}\".",
            )
    await db.flush()
    await _refresh_setup_rating(db, setup_id)
    await db.commit()
    result = await db.execute(
        select(BowlSetupReview)
        .options(selectinload(BowlSetupReview.creator))
        .where(BowlSetupReview.id == review.id)
    )
    return result.scalars().one()


async def get_setup_versions(db: AsyncSession, setup_id: uuid.UUID, user):
    setup = await get_setup_by_id(db, setup_id)
    if setup.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await db.execute(
        select(BowlSetupVersion)
        .where(BowlSetupVersion.bowl_setup_id == setup_id)
        .order_by(BowlSetupVersion.version.desc())
    )
    return result.scalars().all()


async def clone_setup(db: AsyncSession, setup_id: uuid.UUID, user):
    setup = await get_setup_by_id(db, setup_id)
    clone = BowlSetup(
        name=f"{setup.name} copy",
        description=setup.description,
        photo_urls=list(setup.photo_urls or []),
        creator_id=user.id,
        bowl_id=setup.bowl_id,
        kaloud_id=setup.kaloud_id,
        coal_id=setup.coal_id,
        coal_placement_id=setup.coal_placement_id,
        bowl_setup_type_id=setup.bowl_setup_type_id,
        heaviness_score=setup.heaviness_score,
        source_setup_id=setup.id,
    )
    db.add(clone)
    await db.flush()
    for item in setup.tobaccos:
        db.add(BowlSetupTobacco(
            bowl_setup_id=clone.id,
            tobacco_id=item.tobacco_id,
            percentage=item.percentage,
        ))
    await db.commit()
    return await get_setup_by_id(db, clone.id, user.id)


async def set_setup_bookmark(db: AsyncSession, setup_id: uuid.UUID, user, enabled: bool):
    await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(SetupBookmark).where(
            SetupBookmark.user_id == user.id,
            SetupBookmark.bowl_setup_id == setup_id,
        )
    )
    bookmark = result.scalars().first()
    if enabled and not bookmark:
        db.add(SetupBookmark(user_id=user.id, bowl_setup_id=setup_id))
    if not enabled and bookmark:
        await db.delete(bookmark)
    await db.commit()
    return await get_setup_by_id(db, setup_id, user.id)


async def update_setup_review(
    db: AsyncSession,
    setup_id: uuid.UUID,
    review_id: uuid.UUID,
    schema,
    user,
):
    await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(BowlSetupReview)
        .options(selectinload(BowlSetupReview.creator))
        .where(
            BowlSetupReview.id == review_id,
            BowlSetupReview.bowl_setup_id == setup_id,
        )
    )
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if review.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    data = schema.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(review, key, value)

    await db.flush()
    await _refresh_setup_rating(db, setup_id)
    await db.commit()
    await db.refresh(review)
    result = await db.execute(
        select(BowlSetupReview)
        .options(selectinload(BowlSetupReview.creator))
        .where(BowlSetupReview.id == review.id)
    )
    return result.scalars().one()


async def delete_setup_review(
    db: AsyncSession,
    setup_id: uuid.UUID,
    review_id: uuid.UUID,
    user,
):
    await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(BowlSetupReview).where(
            BowlSetupReview.id == review_id,
            BowlSetupReview.bowl_setup_id == setup_id,
        )
    )
    review = result.scalars().first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if review.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    await db.delete(review)
    await db.flush()
    await _refresh_setup_rating(db, setup_id)
    await db.commit()
