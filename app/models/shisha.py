from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Tobacco(Base):
    __tablename__ = "tobaccos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_currency: Mapped[str] = mapped_column(String, nullable=False, default="UAH")
    package_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    setups_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brand: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Coal(Base):
    __tablename__ = "coals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_currency: Mapped[str] = mapped_column(String, nullable=False, default="UAH")
    coals_per_package: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Kaloud(Base):
    __tablename__ = "kalouds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_currency: Mapped[str] = mapped_column(String, nullable=False, default="UAH")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Bowl(Base):
    __tablename__ = "bowls"
    __table_args__ = (
        CheckConstraint(
            "bowl_type IN ('traditional', 'phunnel')",
            name="ck_bowls_bowl_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_currency: Mapped[str] = mapped_column(String, nullable=False, default="UAH")
    capacity_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bowl_type: Mapped[str] = mapped_column(String, nullable=False, default="traditional")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CoalPlacement(Base):
    __tablename__ = "coal_placements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    coal_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BowlSetupType(Base):
    __tablename__ = "bowl_setup_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BowlSetup(Base):
    __tablename__ = "bowl_setups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    bowl_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bowls.id"), nullable=False)
    kaloud_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kalouds.id"), nullable=False
    )
    coal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coals.id"), nullable=False)
    coal_placement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coal_placements.id"), nullable=False
    )
    bowl_setup_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setup_types.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    views_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    heaviness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating_average: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_setup_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bowl_setups.id"), nullable=True
    )

    creator: Mapped["User"] = relationship("User")
    bowl: Mapped["Bowl"] = relationship("Bowl")
    kaloud: Mapped["Kaloud"] = relationship("Kaloud")
    coal: Mapped["Coal"] = relationship("Coal")
    coal_placement: Mapped["CoalPlacement"] = relationship("CoalPlacement")
    bowl_setup_type: Mapped["BowlSetupType"] = relationship("BowlSetupType")

    tobaccos: Mapped[list["BowlSetupTobacco"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["BowlSetupReview"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )
    comments: Mapped[list["BowlSetupComment"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )
    likes: Mapped[list["BowlSetupLike"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )
    views: Mapped[list["BowlSetupView"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )
    versions: Mapped[list["BowlSetupVersion"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )
    contributors: Mapped[list["BowlSetupContributor"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )

    @property
    def average_rating(self) -> float:
        if self.rating_average is not None:
            return round(float(self.rating_average), 1)
        ratings = [review.rating for review in self.reviews or []]
        return round(sum(ratings) / len(ratings), 1) if ratings else 0

    @property
    def contributor_users(self):
        return [contributor.user for contributor in self.contributors or [] if contributor.user]


class BowlSetupView(Base):
    __tablename__ = "bowl_setup_views"
    __table_args__ = (
        UniqueConstraint(
            "bowl_setup_id",
            "ip_address",
            name="uq_bowl_setup_view_ip",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bowl_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setups.id", ondelete="CASCADE"), nullable=False
    )
    ip_address: Mapped[str] = mapped_column(String(64), nullable=False)
    last_viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="views")


class BowlSetupTobacco(Base):
    __tablename__ = "bowl_setup_tobaccos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bowl_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setups.id", ondelete="CASCADE"), nullable=False
    )
    tobacco_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tobaccos.id", ondelete="CASCADE"), nullable=False
    )
    percentage: Mapped[int] = mapped_column(Integer, nullable=False)

    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="tobaccos")
    tobacco: Mapped["Tobacco"] = relationship("Tobacco")


class BowlSetupVersion(Base):
    __tablename__ = "bowl_setup_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bowl_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setups.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="versions")


class BowlSetupReview(Base):
    __tablename__ = "bowl_setup_reviews"
    __table_args__ = (
        UniqueConstraint(
            "bowl_setup_id",
            "creator_id",
            name="uq_bowl_setup_review_creator",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bowl_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setups.id", ondelete="CASCADE"), nullable=False
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="reviews")
    creator: Mapped["User"] = relationship("User")


class ReviewReply(Base):
    __tablename__ = "review_replies"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setup_reviews.id", ondelete="CASCADE"), nullable=False
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    review: Mapped["BowlSetupReview"] = relationship("BowlSetupReview")
    creator: Mapped["User"] = relationship("User")


class BowlSetupComment(Base):
    __tablename__ = "bowl_setup_comments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bowl_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setups.id", ondelete="CASCADE"), nullable=False
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="comments")
    creator: Mapped["User"] = relationship("User")


class BowlSetupLike(Base):
    __tablename__ = "bowl_setup_likes"
    __table_args__ = (
        UniqueConstraint(
            "bowl_setup_id",
            "user_id",
            name="uq_bowl_setup_like_user",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bowl_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="likes")
    user: Mapped["User"] = relationship("User")


class BowlSetupContributor(Base):
    __tablename__ = "bowl_setup_contributors"
    __table_args__ = (
        UniqueConstraint("bowl_setup_id", "user_id", name="uq_setup_contributor_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bowl_setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bowl_setups.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="contributors")
    user: Mapped["User"] = relationship("User")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reporter: Mapped["User"] = relationship("User")
