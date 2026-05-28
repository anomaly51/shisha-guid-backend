import uuid
import re
import html
import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.crud import shisha as crud
from app.models.shisha import (
    Bowl,
    BowlSetup,
    BowlSetupType,
    Coal,
    CoalPlacement,
    Kaloud,
    Report,
    Tobacco,
)
from app.schemas.shisha import ReportResponse
from app.models.user import User
from app.schemas.user import AdminUserResponse, AdminUserUpdate

router = APIRouter(dependencies=[Depends(get_current_admin_user)])

ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
BADGE_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
BADGE_COLORS = (
    "#8B4A2B",
    "#2563EB",
    "#16A34A",
    "#9333EA",
    "#DC2626",
    "#0F766E",
    "#C2410C",
    "#4F46E5",
)
BADGE_EFFECTS = {"none", "frost", "fire", "chemical", "electric", "cosmic", "shimmer"}

CONTENT_MODELS = {
    "bowls": Bowl,
    "tobaccos": Tobacco,
    "coals": Coal,
    "kalouds": Kaloud,
    "coal-placements": CoalPlacement,
    "bowl-setup-types": BowlSetupType,
    "bowl-setups": BowlSetup,
}
REPORT_STATUSES = {"pending", "resolved", "dismissed"}


async def _count(db: AsyncSession, model):
    result = await db.execute(select(func.count()).select_from(model))
    return result.scalar_one()


def _normalize_role(role: str):
    normalized = role.strip().lower()
    if not ROLE_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Role must be an English lowercase identifier",
        )
    return normalized


def _normalize_badge(label: str | None, color: str | None, effect: str | None):
    clean_label = html.escape(" ".join((label or "").split()), quote=False)
    clean_effect = (effect or "none").strip().lower()
    if not clean_label:
        return []
    if clean_effect not in BADGE_EFFECTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown badge effect",
        )
    if len(clean_label) > 28:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Badge label is too long",
        )
    clean_color = (color or "").strip()
    if clean_color:
        if not BADGE_COLOR_PATTERN.fullmatch(clean_color):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Badge color must be a hex color",
            )
        badge_color = clean_color.upper()
    else:
        digest = hashlib.sha256(clean_label.casefold().encode("utf-8")).digest()
        color_seed = int.from_bytes(digest[:4], "big")
        badge_color = BADGE_COLORS[color_seed % len(BADGE_COLORS)]
    return [{
        "label": clean_label,
        "color": badge_color,
        "effect": clean_effect,
    }]


@router.get("/stats")
async def get_admin_stats(db: AsyncSession = Depends(get_db)):
    users_total = await _count(db, User)
    admins_total = (
        await db.execute(
            select(func.count()).select_from(User).where(User.role == "admin")
        )
    ).scalar_one()
    banned_total = (
        await db.execute(
            select(func.count()).select_from(User).where(User.is_banned.is_(True))
        )
    ).scalar_one()
    content = {
        key: await _count(db, model)
        for key, model in CONTENT_MODELS.items()
    }
    return {
        "users_total": users_total,
        "admins_total": admins_total,
        "banned_total": banned_total,
        "content_total": sum(content.values()),
        "content": content,
    }


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.email.asc()))
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    next_role = _normalize_role(payload.role) if payload.role is not None else None

    if user.id == admin.id and (
        (next_role is not None and next_role != "admin") or payload.is_banned is True
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin cannot demote or ban their own account",
        )

    if "nickname" in payload.model_fields_set and payload.nickname:
        payload.nickname = " ".join(payload.nickname.split())
        result = await db.execute(
            select(User.id).where(
                func.lower(User.nickname) == payload.nickname.lower(),
                User.id != user.id,
            )
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nickname is already taken",
            )

    for field in ("nickname", "avatar_url", "is_banned"):
        if field in payload.model_fields_set:
            setattr(user, field, getattr(payload, field))
    if next_role is not None:
        user.role = next_role
    if "badge_label" in payload.model_fields_set or payload.badges is not None:
        label = payload.badge_label
        if label is None and payload.badges is not None:
            label = payload.badges[0] if payload.badges else None
        user.badges = _normalize_badge(label, payload.badge_color, payload.badge_effect)

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/content")
async def list_content(db: AsyncSession = Depends(get_db)):
    content = {}
    for key, model in CONTENT_MODELS.items():
        query = select(model)
        if hasattr(model, "deleted_at"):
            query = query.where(model.deleted_at.is_(None))
        result = await db.execute(
            query.order_by(model.created_at.desc()).limit(50)
        )
        content[key] = [
            {
                "id": str(item.id),
                "name": item.name,
                "description": item.description,
                "creator_id": str(item.creator_id),
                "created_at": item.created_at,
            }
            for item in result.scalars().all()
        ]
    return content


@router.delete(
    "/content/{content_type}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_content(
    content_type: str,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    model = CONTENT_MODELS.get(content_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await crud.delete_item(db, model, item_id)


@router.get("/reports", response_model=list[ReportResponse])
async def list_reports(
    status_filter: str = "pending",
    db: AsyncSession = Depends(get_db),
):
    if status_filter not in REPORT_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    result = await db.execute(
        select(Report)
        .options(selectinload(Report.reporter))
        .where(Report.status == status_filter)
        .order_by(Report.created_at.desc())
        .limit(100)
    )
    return result.scalars().all()


@router.patch("/reports/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: uuid.UUID,
    status_value: str = "resolved",
    db: AsyncSession = Depends(get_db),
):
    if status_value not in (REPORT_STATUSES - {"pending"}):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    report.status = status_value
    report.resolved_at = datetime.utcnow()
    await db.commit()
    result = await db.execute(
        select(Report).options(selectinload(Report.reporter)).where(Report.id == report.id)
    )
    return result.scalars().one()
