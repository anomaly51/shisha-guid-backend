import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    get_current_admin_user,
    get_current_user,
    get_optional_current_user,
)
from app.crud import shisha as crud
from app.models.shisha import BowlSetup, BowlSetupType, CoalPlacement
from app.models.user import User
from app.schemas.shisha import (
    BowlSetupCreate,
    BowlSetupPageResponse,
    BowlSetupReviewCreate,
    BowlSetupReviewResponse,
    BowlSetupResponse,
    BowlSetupTypeCreate,
    BowlSetupTypeResponse,
    BowlSetupVersionResponse,
    CoalPlacementCreate,
    CoalPlacementResponse,
)

router = APIRouter()


@router.get("/coal-placements", response_model=list[CoalPlacementResponse])
async def get_coal_placements(
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await crud.get_all(db, CoalPlacement, limit=limit, offset=offset)


@router.post(
    "/coal-placements",
    response_model=CoalPlacementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_coal_placement(
    item: CoalPlacementCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin_user),
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
    user: User = Depends(get_current_admin_user),
):
    return await crud.update_item_for_user(db, CoalPlacement, item_id, item, user)


@router.delete("/coal-placements/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_coal_placement(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin_user),
):
    await crud.delete_item_for_user(db, CoalPlacement, item_id, user)


@router.get("/bowl-setup-types", response_model=list[BowlSetupTypeResponse])
async def get_bowl_setup_types(
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await crud.get_all(db, BowlSetupType, limit=limit, offset=offset)


@router.post(
    "/bowl-setup-types",
    response_model=BowlSetupTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bowl_setup_type(
    item: BowlSetupTypeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin_user),
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
    user: User = Depends(get_current_admin_user),
):
    return await crud.update_item_for_user(db, BowlSetupType, item_id, item, user)


@router.delete("/bowl-setup-types/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bowl_setup_type(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin_user),
):
    await crud.delete_item_for_user(db, BowlSetupType, item_id, user)


@router.get("/bowl-setups", response_model=list[BowlSetupResponse] | BowlSetupPageResponse)
async def get_bowl_setups(
    tobacco_ids: list[uuid.UUID] = Query(default_factory=list),
    search: str | None = Query(default=None, min_length=1),
    creator_id: uuid.UUID | None = Query(default=None),
    bookmarked: bool = Query(default=False),
    following: bool = Query(default=False),
    strength: Literal["all", "light", "medium", "strong", "heavy"] = "all",
    sort: Literal[
        "newest",
        "rating",
        "views",
        "strengthDesc",
        "strengthAsc",
        "name",
    ] = "newest",
    limit: int | None = Query(default=None, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    if (bookmarked or following) and not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    bookmarked_by = user.id if bookmarked and user else None
    followed_by = user.id if following and user else None
    if limit is not None:
        return await crud.get_setups_page(
            db,
            tobacco_ids,
            strength,
            sort,
            limit,
            offset,
            search=search,
            creator_id=creator_id,
            bookmarked_by=bookmarked_by,
            followed_by=followed_by,
            user_id=user.id if user else None,
        )
    return await crud.get_all_setups(
        db,
        tobacco_ids,
        strength,
        sort,
        search=search,
        creator_id=creator_id,
        bookmarked_by=bookmarked_by,
        followed_by=followed_by,
        user_id=user.id if user else None,
    )


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


def _get_client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


@router.get("/bowl-setups/{item_id}", response_model=BowlSetupResponse)
async def get_bowl_setup(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    return await crud.get_setup_by_id(db, item_id, user.id if user else None)


@router.post("/bowl-setups/{item_id}/views", response_model=BowlSetupResponse)
async def record_bowl_setup_view(
    item_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_current_user),
):
    setup = await crud.get_setup_by_id(db, item_id)
    return await crud.record_setup_view(
        db,
        setup,
        _get_client_ip(request),
        user.id if user else None,
    )


@router.patch("/bowl-setups/{item_id}", response_model=BowlSetupResponse)
async def update_bowl_setup(
    item_id: uuid.UUID,
    item: BowlSetupCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.update_setup_for_user(db, item_id, item, user)


@router.delete("/bowl-setups/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bowl_setup(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_item_for_user(db, BowlSetup, item_id, user)


@router.get(
    "/bowl-setups/{item_id}/reviews",
    response_model=list[BowlSetupReviewResponse],
)
async def get_bowl_setup_reviews(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await crud.get_setup_reviews(db, item_id)


@router.post(
    "/bowl-setups/{item_id}/reviews",
    response_model=BowlSetupReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_bowl_setup_review(
    item_id: uuid.UUID,
    item: BowlSetupReviewCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.create_setup_review(db, item_id, item, user)


@router.patch(
    "/bowl-setups/{item_id}/reviews/{review_id}",
    response_model=BowlSetupReviewResponse,
)
async def update_bowl_setup_review(
    item_id: uuid.UUID,
    review_id: uuid.UUID,
    item: BowlSetupReviewCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.update_setup_review(db, item_id, review_id, item, user)


@router.delete(
    "/bowl-setups/{item_id}/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_bowl_setup_review(
    item_id: uuid.UUID,
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await crud.delete_setup_review(db, item_id, review_id, user)


@router.get(
    "/bowl-setups/{item_id}/versions",
    response_model=list[BowlSetupVersionResponse],
)
async def get_bowl_setup_versions(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.get_setup_versions(db, item_id, user)


@router.post("/bowl-setups/{item_id}/clone", response_model=BowlSetupResponse)
async def clone_bowl_setup(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.clone_setup(db, item_id, user)


@router.post("/bowl-setups/{item_id}/bookmark", response_model=BowlSetupResponse)
async def bookmark_bowl_setup(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.set_setup_bookmark(db, item_id, user, True)


@router.delete("/bowl-setups/{item_id}/bookmark", response_model=BowlSetupResponse)
async def unbookmark_bowl_setup(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await crud.set_setup_bookmark(db, item_id, user, False)
