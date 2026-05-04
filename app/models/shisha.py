from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Tobacco(Base):
    __tablename__ = "tobaccos"

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


class Coal(Base):
    __tablename__ = "coals"

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


class Kaloud(Base):
    __tablename__ = "kalouds"

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


class Bowl(Base):
    __tablename__ = "bowls"

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


class CoalPlacement(Base):
    __tablename__ = "coal_placements"

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


class BowlSetup(Base):
    __tablename__ = "bowl_setups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

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

    # ORM Relationships
    creator: Mapped["User"] = relationship("User")
    bowl: Mapped["Bowl"] = relationship("Bowl")
    kaloud: Mapped["Kaloud"] = relationship("Kaloud")
    coal: Mapped["Coal"] = relationship("Coal")
    coal_placement: Mapped["CoalPlacement"] = relationship("CoalPlacement")
    bowl_setup_type: Mapped["BowlSetupType"] = relationship("BowlSetupType")

    # Связь Many-to-Many с табаками через объект-ассоциацию (учитываем percentage)
    tobaccos: Mapped[list["BowlSetupTobacco"]] = relationship(
        back_populates="bowl_setup", cascade="all, delete-orphan"
    )


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

    # ORM Relationships
    bowl_setup: Mapped["BowlSetup"] = relationship(back_populates="tobaccos")
    tobacco: Mapped["Tobacco"] = relationship("Tobacco")
