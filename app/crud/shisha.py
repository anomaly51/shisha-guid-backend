import asyncio
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import distinct, func, literal, update, union_all
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.storage import duplicate_uploaded_media_url, extract_object_path, promote_file
from app.core.email import send_email
from app.models.shisha import (
    BowlSetup,
    BowlSetupComment,
    BowlSetupContributor,
    BowlSetupLike,
    BowlSetupReview,
    BowlSetupTobacco,
    BowlSetupVersion,
    BowlSetupView,
    Report,
    ReviewReply,
    Tobacco,
)
from app.models.user import Notification, SetupBookmark, User, UserFollow
from app.utils.strength import STRENGTH_RANGES, clamp as _clamp, get_tobacco_strength


logger = logging.getLogger(__name__)
VIEW_INTERVAL = timedelta(minutes=30)

AUTO_BADGES = {
    "first_setup": {"label": "Первая забивка", "color": "#16A34A", "effect": "shimmer"},
    "ten_setups": {"label": "10 забивок", "color": "#2563EB", "effect": "electric"},
    "first_review": {"label": "Первый отзыв", "color": "#9333EA", "effect": "cosmic"},
    "hundred_views": {"label": "100 просмотров", "color": "#DC2626", "effect": "fire"},
}


async def _send_email_async(to: str, subject: str, body: str) -> None:
    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, send_email, to, subject, body)
    except Exception:
        logger.exception("Failed to send notification email")


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


def _notification(
    *,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    bowl_setup_id: uuid.UUID | None,
    notification_type: str,
    title: str,
    body: str,
) -> Notification:
    return Notification(
        user_id=user_id,
        actor_id=actor_id,
        bowl_setup_id=bowl_setup_id,
        type=notification_type,
        title=title,
        body=body,
    )


def _snapshot_setup(setup: BowlSetup) -> dict:
    photo_urls = setup.photo_urls or []
    return {
        "name": setup.name,
        "description": setup.description,
        "photo_urls": photo_urls,
        "photo_object_paths": [extract_object_path(url) for url in photo_urls],
        "tags": setup.tags or [],
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


def _award_badge(user: User, key: str) -> None:
    badge = AUTO_BADGES[key]
    badges = list(user.badges or [])
    if any(item.get("label") == badge["label"] for item in badges):
        return
    user.badges = [*badges, badge]


def _touch_user_activity(user: User, *, score_delta: int = 0, publish_activity: bool = False) -> None:
    now = datetime.utcnow()
    if publish_activity:
        last_active = user.last_active_at
        if last_active is None:
            user.streak_days = 1
        elif last_active.date() == now.date():
            user.streak_days = max(user.streak_days or 1, 1)
        elif last_active.date() == (now - timedelta(days=1)).date():
            user.streak_days = (user.streak_days or 0) + 1
        else:
            user.streak_days = 1
        user.last_active_at = now
    user.score = max(0, int(user.score or 0) + score_delta)


async def _decorate_setups(
    db: AsyncSession,
    setups: list[BowlSetup],
    user_id: uuid.UUID | None = None,
) -> list[BowlSetup]:
    if not setups:
        return setups

    creator_ids = {setup.creator_id for setup in setups}
    setup_ids = [setup.id for setup in setups]
    counts_query = union_all(
        select(
            literal("creator").label("kind"),
            BowlSetup.creator_id.label("entity_id"),
            func.count(BowlSetup.id).label("count_value"),
        )
        .where(BowlSetup.creator_id.in_(creator_ids))
        .group_by(BowlSetup.creator_id),
        select(
            literal("likes").label("kind"),
            BowlSetupLike.bowl_setup_id.label("entity_id"),
            func.count(BowlSetupLike.id).label("count_value"),
        )
        .where(BowlSetupLike.bowl_setup_id.in_(setup_ids))
        .group_by(BowlSetupLike.bowl_setup_id),
        select(
            literal("comments").label("kind"),
            BowlSetupComment.bowl_setup_id.label("entity_id"),
            func.count(BowlSetupComment.id).label("count_value"),
        )
        .where(BowlSetupComment.bowl_setup_id.in_(setup_ids))
        .group_by(BowlSetupComment.bowl_setup_id),
        select(
            literal("clones").label("kind"),
            BowlSetup.source_setup_id.label("entity_id"),
            func.count(BowlSetup.id).label("count_value"),
        )
        .where(BowlSetup.source_setup_id.in_(setup_ids))
        .group_by(BowlSetup.source_setup_id),
    ).subquery()
    counts_result = await db.execute(select(counts_query.c.kind, counts_query.c.entity_id, counts_query.c.count_value))
    setup_counts: dict[uuid.UUID, int] = {}
    likes_counts: dict[uuid.UUID, int] = {}
    comments_counts: dict[uuid.UUID, int] = {}
    clones_counts: dict[uuid.UUID, int] = {}
    for kind, entity_id, count in counts_result.all():
        if kind == "creator":
            setup_counts[entity_id] = int(count)
        elif kind == "likes":
            likes_counts[entity_id] = int(count)
        elif kind == "comments":
            comments_counts[entity_id] = int(count)
        elif kind == "clones":
            clones_counts[entity_id] = int(count)

    bookmarked_ids: set[uuid.UUID] = set()
    liked_ids: set[uuid.UUID] = set()
    followed_creator_ids: set[uuid.UUID] = set()
    if user_id:
        bookmark_result = await db.execute(
            select(SetupBookmark.bowl_setup_id).where(
                SetupBookmark.user_id == user_id,
                SetupBookmark.bowl_setup_id.in_(setup_ids),
            )
        )
        bookmarked_ids = set(bookmark_result.scalars().all())
        like_result = await db.execute(
            select(BowlSetupLike.bowl_setup_id).where(
                BowlSetupLike.user_id == user_id,
                BowlSetupLike.bowl_setup_id.in_(setup_ids),
            )
        )
        liked_ids = set(like_result.scalars().all())
        follow_result = await db.execute(
            select(UserFollow.followed_id).where(
                UserFollow.follower_id == user_id,
                UserFollow.followed_id.in_(creator_ids),
            )
        )
        followed_creator_ids = set(follow_result.scalars().all())

    for setup in setups:
        if setup.creator:
            setattr(setup.creator, "setups_count", setup_counts.get(setup.creator_id, 0))
            setattr(setup.creator, "is_following", setup.creator_id in followed_creator_ids)
        setattr(setup, "is_bookmarked", setup.id in bookmarked_ids)
        setattr(setup, "is_liked", setup.id in liked_ids)
        setattr(setup, "likes_count", likes_counts.get(setup.id, 0))
        setattr(setup, "comments_count", comments_counts.get(setup.id, 0))
        setattr(setup, "clones_count", clones_counts.get(setup.id, 0))
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
    await db.execute(
        update(BowlSetup)
        .where(BowlSetup.id == setup_id)
        .values(
            rating_average=round(float(average or 0), 1),
            rating_count=int(count or 0),
        )
    )


async def _refresh_tobacco_setup_counts(db: AsyncSession, tobacco_ids: set[uuid.UUID]) -> None:
    if not tobacco_ids:
        return
    counts_result = await db.execute(
        select(BowlSetupTobacco.tobacco_id, func.count(distinct(BowlSetupTobacco.bowl_setup_id)))
        .where(BowlSetupTobacco.tobacco_id.in_(tobacco_ids))
        .group_by(BowlSetupTobacco.tobacco_id)
    )
    counts = {tobacco_id: int(count) for tobacco_id, count in counts_result.all()}
    for tobacco_id in tobacco_ids:
        await db.execute(
            update(Tobacco)
            .where(Tobacco.id == tobacco_id)
            .values(setups_count=counts.get(tobacco_id, 0))
        )


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
    period: str | None = None,
    tags: list[str] | None = None,
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
        period=period,
        tags=tags,
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
    period: str | None = None,
    tags: list[str] | None = None,
):
    limit = max(1, min(limit or 50, 50))
    offset = max(0, offset)
    selected_tobacco_ids = list(dict.fromkeys(tobacco_ids or []))

    query = select(BowlSetup).options(
        selectinload(BowlSetup.tobaccos).selectinload(BowlSetupTobacco.tobacco),
        selectinload(BowlSetup.creator),
        selectinload(BowlSetup.contributors).selectinload(BowlSetupContributor.user),
    )
    query = query.join(User, User.id == BowlSetup.creator_id).where(User.is_banned.is_(False))

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
    if period == "week":
        query = query.where(BowlSetup.created_at >= datetime.utcnow() - timedelta(days=7))
    selected_tags = [tag.strip().lower() for tag in (tags or []) if tag.strip()]
    if selected_tags:
        query = query.where(BowlSetup.tags.contains(selected_tags))

    if strength and strength != "all":
        strength_range = STRENGTH_RANGES.get(strength)
        if strength_range:
            query = query.where(
                BowlSetup.heaviness_score >= strength_range[0],
                BowlSetup.heaviness_score <= strength_range[1],
            )

    if sort == "views":
        query = query.order_by(BowlSetup.views_count.desc(), BowlSetup.created_at.desc())
    elif sort == "rating":
        query = query.order_by(BowlSetup.rating_average.desc(), BowlSetup.created_at.desc())
    elif sort == "strengthDesc":
        query = query.order_by(
            BowlSetup.heaviness_score.desc().nullslast(),
            BowlSetup.created_at.desc(),
        )
    elif sort == "strengthAsc":
        query = query.order_by(
            BowlSetup.heaviness_score.asc().nullslast(),
            BowlSetup.created_at.desc(),
        )
    elif sort == "name":
        query = query.order_by(func.lower(BowlSetup.name), BowlSetup.created_at.desc())
    else:
        query = query.order_by(BowlSetup.is_featured.desc(), BowlSetup.created_at.desc())

    result = await db.execute(
        query.add_columns(func.count().over().label("_total")).offset(offset).limit(limit)
    )
    rows = result.all()
    items = [row[0] for row in rows]
    total = int(rows[0][1] or 0) if rows else 0
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
            selectinload(BowlSetup.contributors).selectinload(BowlSetupContributor.user),
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

    statement = (
        insert(BowlSetupView)
        .values(bowl_setup_id=setup.id, ip_address=normalized_ip, last_viewed_at=now)
        .on_conflict_do_update(
            index_elements=["bowl_setup_id", "ip_address"],
            set_={"last_viewed_at": now},
            where=BowlSetupView.last_viewed_at <= cutoff,
        )
        .returning(BowlSetupView.id)
    )
    insert_result = await db.execute(statement)
    counted = insert_result.scalar_one_or_none() is not None

    if not counted:
        return setup

    await db.execute(
        update(BowlSetup)
        .where(BowlSetup.id == setup.id)
        .values(views_count=BowlSetup.views_count + 1)
    )
    owner = await db.get(User, setup.creator_id)
    if owner and int(setup.views_count or 0) + 1 >= 100:
        _award_badge(owner, "hundred_views")
        db.add(owner)
    await db.commit()
    return await get_setup_by_id(db, setup.id)


async def create_setup(db: AsyncSession, schema, user_id: uuid.UUID):
    user = await db.get(User, user_id)
    data = schema.model_dump(exclude={"tobaccos"})
    data["photo_urls"] = [
        promote_file(url, "bowl_setups", str(user_id)) for url in data.get("photo_urls", [])
    ]
    data["heaviness_score"] = await _calculate_heaviness_score(db, schema.tobaccos)
    setup = BowlSetup(**data, creator_id=user_id)
    try:
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
        await db.flush()
        await _refresh_tobacco_setup_counts(db, {item.tobacco_id for item in schema.tobaccos})
        if user:
            setups_count = await db.scalar(
                select(func.count(BowlSetup.id)).where(BowlSetup.creator_id == user_id)
            )
            _touch_user_activity(user, score_delta=10, publish_activity=True)
            if int(setups_count or 0) >= 1:
                _award_badge(user, "first_setup")
            if int(setups_count or 0) >= 10:
                _award_badge(user, "ten_setups")
            db.add(user)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return await get_setup_by_id(db, setup.id)


async def update_setup(db: AsyncSession, item_id: uuid.UUID, schema):
    setup = await get_setup_by_id(db, item_id)
    old_tobacco_ids = {item.tobacco_id for item in setup.tobaccos}
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
    await _refresh_tobacco_setup_counts(
        db,
        old_tobacco_ids | {item.tobacco_id for item in schema.tobaccos},
    )
    await db.commit()
    return await get_setup_by_id(db, setup.id)


async def update_setup_for_user(db: AsyncSession, item_id: uuid.UUID, schema, user):
    setup = await get_setup_by_id(db, item_id)
    old_tobacco_ids = {item.tobacco_id for item in setup.tobaccos}
    is_contributor = bool(await db.scalar(
        select(BowlSetupContributor.id).where(
            BowlSetupContributor.bowl_setup_id == item_id,
            BowlSetupContributor.user_id == user.id,
        )
    ))
    if setup.creator_id != user.id and user.role != "admin" and not is_contributor:
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
    await _refresh_tobacco_setup_counts(
        db,
        old_tobacco_ids | {item.tobacco_id for item in schema.tobaccos},
    )
    await db.commit()
    return await get_setup_by_id(db, setup.id)


async def set_setup_featured(db: AsyncSession, item_id: uuid.UUID, featured: bool):
    setup = await get_setup_by_id(db, item_id)
    setup.is_featured = featured
    await db.commit()
    return await get_setup_by_id(db, setup.id)


async def add_setup_contributor(db: AsyncSession, setup_id: uuid.UUID, nickname: str, user):
    setup = await get_setup_by_id(db, setup_id)
    if setup.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    normalized = nickname.strip()
    contributor_user = await db.scalar(
        select(User).where(func.lower(User.nickname) == normalized.lower())
    )
    if not contributor_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if contributor_user.id == setup.creator_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Creator is already the author")
    existing = await db.scalar(
        select(BowlSetupContributor.id).where(
            BowlSetupContributor.bowl_setup_id == setup_id,
            BowlSetupContributor.user_id == contributor_user.id,
        )
    )
    if not existing:
        db.add(BowlSetupContributor(bowl_setup_id=setup_id, user_id=contributor_user.id))
        db.add(_notification(
            user_id=contributor_user.id,
            actor_id=user.id,
            bowl_setup_id=setup.id,
            notification_type="setup_contributor_added",
            title="Added as contributor",
            body=f"{user.display_name} added you as a contributor to {setup.name}.",
        ))
        await db.commit()
    return await get_setup_by_id(db, setup_id, user.id)


async def remove_setup_contributor(db: AsyncSession, setup_id: uuid.UUID, contributor_id: uuid.UUID, user):
    setup = await get_setup_by_id(db, setup_id)
    if setup.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    contributor = await db.scalar(
        select(BowlSetupContributor).where(
            BowlSetupContributor.bowl_setup_id == setup_id,
            BowlSetupContributor.user_id == contributor_id,
        )
    )
    if contributor:
        await db.delete(contributor)
        await db.commit()
    return await get_setup_by_id(db, setup_id, user.id)


async def delete_setup_for_user(db: AsyncSession, item_id: uuid.UUID, user):
    setup = await get_setup_by_id(db, item_id)
    if setup.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    tobacco_ids = {item.tobacco_id for item in setup.tobaccos}
    await db.delete(setup)
    await db.flush()
    await _refresh_tobacco_setup_counts(db, tobacco_ids)
    await db.commit()


async def get_setup_reviews(
    db: AsyncSession,
    setup_id: uuid.UUID,
    limit: int | None = None,
    offset: int = 0,
):
    await get_setup_by_id(db, setup_id)
    safe_limit = max(1, min(limit or 50, 50))
    safe_offset = max(0, offset)
    result = await db.execute(
        select(BowlSetupReview)
        .options(selectinload(BowlSetupReview.creator))
        .where(BowlSetupReview.bowl_setup_id == setup_id)
        .order_by(BowlSetupReview.created_at.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    reviews = result.scalars().all()
    if reviews:
        counts_result = await db.execute(
            select(ReviewReply.review_id, func.count(ReviewReply.id))
            .where(ReviewReply.review_id.in_([review.id for review in reviews]))
            .group_by(ReviewReply.review_id)
        )
        counts = {review_id: int(count) for review_id, count in counts_result.all()}
        for review in reviews:
            setattr(review, "replies_count", counts.get(review.id, 0))
    return reviews


async def get_review_replies(db: AsyncSession, setup_id: uuid.UUID, review_id: uuid.UUID):
    await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(ReviewReply)
        .options(selectinload(ReviewReply.creator))
        .join(BowlSetupReview, BowlSetupReview.id == ReviewReply.review_id)
        .where(
            BowlSetupReview.id == review_id,
            BowlSetupReview.bowl_setup_id == setup_id,
        )
        .order_by(ReviewReply.created_at.asc())
    )
    return result.scalars().all()


async def create_review_reply(db: AsyncSession, setup_id: uuid.UUID, review_id: uuid.UUID, schema, user):
    setup = await get_setup_by_id(db, setup_id)
    review = await db.scalar(
        select(BowlSetupReview).where(
            BowlSetupReview.id == review_id,
            BowlSetupReview.bowl_setup_id == setup_id,
        )
    )
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if setup.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    reply = ReviewReply(review_id=review_id, creator_id=user.id, body=schema.body.strip())
    db.add(reply)
    if review.creator_id != user.id:
        db.add(_notification(
            user_id=review.creator_id,
            actor_id=user.id,
            bowl_setup_id=setup.id,
            notification_type="review_reply",
            title="Review reply",
            body=f"{user.display_name} replied to your review on {setup.name}.",
        ))
    await db.commit()
    result = await db.execute(
        select(ReviewReply)
        .options(selectinload(ReviewReply.creator))
        .where(ReviewReply.id == reply.id)
    )
    return result.scalars().one()


async def delete_review_reply(db: AsyncSession, setup_id: uuid.UUID, review_id: uuid.UUID, reply_id: uuid.UUID, user):
    setup = await get_setup_by_id(db, setup_id)
    reply = await db.scalar(
        select(ReviewReply)
        .join(BowlSetupReview, BowlSetupReview.id == ReviewReply.review_id)
        .where(
            ReviewReply.id == reply_id,
            ReviewReply.review_id == review_id,
            BowlSetupReview.bowl_setup_id == setup_id,
        )
    )
    if not reply:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if reply.creator_id != user.id and setup.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await db.delete(reply)
    await db.commit()


async def get_setup_comments(db: AsyncSession, setup_id: uuid.UUID):
    await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(BowlSetupComment)
        .options(selectinload(BowlSetupComment.creator))
        .where(BowlSetupComment.bowl_setup_id == setup_id)
        .order_by(BowlSetupComment.created_at.desc())
    )
    return result.scalars().all()


async def create_setup_comment(db: AsyncSession, setup_id: uuid.UUID, schema, user):
    setup = await get_setup_by_id(db, setup_id)
    comment = BowlSetupComment(
        bowl_setup_id=setup_id,
        creator_id=user.id,
        body=schema.body.strip(),
    )
    db.add(comment)
    if setup.creator_id != user.id:
        db.add(_notification(
            user_id=setup.creator_id,
            actor_id=user.id,
            bowl_setup_id=setup.id,
            notification_type="setup_comment",
            title="New setup comment",
            body=f"{user.display_name} (/users/{user.id}) commented on your setup {setup.name}.",
        ))
    await db.commit()
    result = await db.execute(
        select(BowlSetupComment)
        .options(selectinload(BowlSetupComment.creator))
        .where(BowlSetupComment.id == comment.id)
    )
    return result.scalars().one()


async def delete_setup_comment(db: AsyncSession, setup_id: uuid.UUID, comment_id: uuid.UUID, user):
    result = await db.execute(
        select(BowlSetupComment).where(
            BowlSetupComment.id == comment_id,
            BowlSetupComment.bowl_setup_id == setup_id,
        )
    )
    comment = result.scalars().first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if comment.creator_id != user.id and user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await db.delete(comment)
    await db.commit()


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
    daily_count = await db.scalar(
        select(func.count(BowlSetupReview.id)).where(
            BowlSetupReview.creator_id == user.id,
            BowlSetupReview.created_at >= datetime.utcnow() - timedelta(days=1),
        )
    )
    if int(daily_count or 0) >= settings.REVIEW_RATE_LIMIT_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily review limit reached",
        )

    review = BowlSetupReview(
        bowl_setup_id=setup_id,
        creator_id=user.id,
        **schema.model_dump(),
    )
    db.add(review)
    await db.flush()
    _touch_user_activity(user, score_delta=2, publish_activity=True)
    review_count = await db.scalar(
        select(func.count(BowlSetupReview.id)).where(BowlSetupReview.creator_id == user.id)
    )
    if int(review_count or 0) <= 1:
        _award_badge(user, "first_review")
    db.add(user)
    if setup.creator_id != user.id:
        notification = Notification(
            user_id=setup.creator_id,
            actor_id=user.id,
            bowl_setup_id=setup.id,
            type="setup_review",
            title="New setup review",
            body=f"{user.display_name} (/users/{user.id}) reviewed your setup {setup.name}.",
        )
        db.add(notification)
        owner = await db.get(User, setup.creator_id)
        if owner:
            await _send_email_async(
                owner.email,
                "New review on your ShishaGuid setup",
                f"{user.display_name} (/users/{user.id}) reviewed your setup \"{setup.name}\".",
            )
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
    clone_id = uuid.uuid4()
    clone = BowlSetup(
        id=clone_id,
        name=f"{setup.name} copy",
        description=setup.description,
        photo_urls=[
            duplicate_uploaded_media_url(url, "bowl_setups", str(user.id), f"{clone_id}-{index}-{url.split('/')[-1]}")
            for index, url in enumerate(setup.photo_urls or [])
        ],
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
    await _refresh_tobacco_setup_counts(db, {item.tobacco_id for item in setup.tobaccos})
    if setup.creator_id != user.id:
        db.add(_notification(
            user_id=setup.creator_id,
            actor_id=user.id,
            bowl_setup_id=setup.id,
            notification_type="setup_cloned",
            title="Setup cloned",
            body=f"{user.display_name} (/users/{user.id}) cloned your setup {setup.name}.",
        ))
    await db.commit()
    return await get_setup_by_id(db, clone.id, user.id)


async def set_setup_bookmark(db: AsyncSession, setup_id: uuid.UUID, user, enabled: bool):
    setup = await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(SetupBookmark).where(
            SetupBookmark.user_id == user.id,
            SetupBookmark.bowl_setup_id == setup_id,
        )
    )
    bookmark = result.scalars().first()
    if enabled and not bookmark:
        db.add(SetupBookmark(user_id=user.id, bowl_setup_id=setup_id))
        if setup.creator_id != user.id:
            db.add(_notification(
                user_id=setup.creator_id,
                actor_id=user.id,
                bowl_setup_id=setup.id,
                notification_type="setup_bookmarked",
                title="Setup bookmarked",
                body=f"{user.display_name} (/users/{user.id}) bookmarked your setup {setup.name}.",
            ))
    if not enabled and bookmark:
        await db.delete(bookmark)
    await db.commit()
    return await get_setup_by_id(db, setup_id, user.id)


async def set_setup_like(db: AsyncSession, setup_id: uuid.UUID, user, enabled: bool):
    setup = await get_setup_by_id(db, setup_id)
    result = await db.execute(
        select(BowlSetupLike).where(
            BowlSetupLike.user_id == user.id,
            BowlSetupLike.bowl_setup_id == setup_id,
        )
    )
    like = result.scalars().first()
    if enabled and not like:
        db.add(BowlSetupLike(user_id=user.id, bowl_setup_id=setup_id))
        if setup.creator_id != user.id:
            owner = await db.get(User, setup.creator_id)
            if owner:
                _touch_user_activity(owner, score_delta=1)
                db.add(owner)
    if not enabled and like:
        await db.delete(like)
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


async def create_report(db: AsyncSession, schema, user):
    if schema.target_type == "setup":
        await get_setup_by_id(db, schema.target_id)
    elif schema.target_type == "review":
        review = await db.get(BowlSetupReview, schema.target_id)
        if not review:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    report = Report(
        target_type=schema.target_type,
        target_id=schema.target_id,
        reporter_id=user.id,
        reason=schema.reason.strip(),
    )
    db.add(report)
    await db.commit()
    result = await db.execute(
        select(Report)
        .options(selectinload(Report.reporter))
        .where(Report.id == report.id)
    )
    return result.scalars().one()
