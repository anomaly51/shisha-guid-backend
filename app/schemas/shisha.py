from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field

from app.schemas.user import UserBadge


class ComponentBase(BaseModel):
    name: str
    description: str | None = None
    photo_urls: list[str] = Field(default_factory=list)


class ComponentCreate(ComponentBase):
    pass


class ComponentResponse(ComponentBase):
    id: UUID4
    creator_id: UUID4
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PricedComponentBase(ComponentBase):
    price: int = Field(..., ge=0)
    price_currency: str = Field(default="UAH", pattern="^UAH$")


class PricedComponentCreate(PricedComponentBase):
    pass


class PricedComponentResponse(PricedComponentBase):
    id: UUID4
    creator_id: UUID4
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TobaccoBase(PricedComponentBase):
    package_grams: int | None = Field(default=None, ge=1)
    strength: int | None = Field(default=None, ge=0, le=10)


class TobaccoCreate(TobaccoBase):
    pass


class TobaccoResponse(TobaccoBase):
    id: UUID4
    creator_id: UUID4
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoalBase(PricedComponentBase):
    coals_per_package: int | None = Field(default=None, ge=1)


class CoalCreate(CoalBase):
    pass


class CoalResponse(CoalBase):
    id: UUID4
    creator_id: UUID4
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KaloudCreate(PricedComponentCreate):
    pass


class KaloudResponse(PricedComponentResponse):
    pass


class BowlBase(PricedComponentBase):
    capacity_grams: int | None = Field(default=None, ge=1)
    bowl_type: str = Field(default="traditional", pattern="^(traditional|phunnel)$")


class BowlCreate(BowlBase):
    pass


class BowlResponse(BowlBase):
    id: UUID4
    creator_id: UUID4
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoalPlacementBase(ComponentBase):
    coal_count: int | None = Field(default=None, ge=1)


class CoalPlacementCreate(CoalPlacementBase):
    pass


class CoalPlacementResponse(CoalPlacementBase):
    id: UUID4
    creator_id: UUID4
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BowlSetupTypeCreate(ComponentCreate):
    pass


class BowlSetupTypeResponse(ComponentResponse):
    pass


class BowlSetupTobaccoCreate(BaseModel):
    tobacco_id: UUID4
    percentage: int = Field(..., ge=1, le=100)


class BowlSetupTobaccoResponse(BaseModel):
    id: UUID4
    tobacco_id: UUID4
    percentage: int

    model_config = ConfigDict(from_attributes=True)


class PublicCreatorResponse(BaseModel):
    id: UUID4
    email: str
    nickname: str | None = None
    avatar_url: str | None = None
    role: str = "user"
    badges: list[UserBadge] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BowlSetupBase(BaseModel):
    name: str
    description: str | None = None
    bowl_id: UUID4
    kaloud_id: UUID4
    coal_id: UUID4
    coal_placement_id: UUID4
    bowl_setup_type_id: UUID4


class BowlSetupCreate(BowlSetupBase):
    tobaccos: list[BowlSetupTobaccoCreate] = Field(..., min_length=1)


class BowlSetupResponse(BowlSetupBase):
    id: UUID4
    creator_id: UUID4
    creator: PublicCreatorResponse | None = None
    created_at: datetime
    views_count: int = 0
    average_rating: float = 0
    tobaccos: list[BowlSetupTobaccoResponse]

    model_config = ConfigDict(from_attributes=True)


class BowlSetupPageResponse(BaseModel):
    items: list[BowlSetupResponse]
    total: int
    limit: int
    offset: int
    has_more: bool

    model_config = ConfigDict(from_attributes=True)


class BowlSetupReviewCreate(BaseModel):
    rating: float = Field(..., ge=1, le=10, multiple_of=0.5)
    description: str = Field(..., min_length=3, max_length=2000)


class BowlSetupReviewResponse(BaseModel):
    id: UUID4
    bowl_setup_id: UUID4
    creator_id: UUID4
    creator: PublicCreatorResponse | None = None
    rating: float
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
