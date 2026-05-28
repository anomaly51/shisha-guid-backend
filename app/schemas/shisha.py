from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.storage import is_uploaded_media_url
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
    brand: str | None = Field(default=None, max_length=80)
    package_grams: int | None = Field(default=None, ge=1)
    strength: int | None = Field(default=None, ge=0, le=10)


class TobaccoCreate(TobaccoBase):
    pass


class TobaccoResponse(TobaccoBase):
    id: UUID4
    creator_id: UUID4
    created_at: datetime
    setups_count: int = 0
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True)


class TobaccoListItem(BaseModel):
    id: UUID4
    name: str
    brand: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    price: int = Field(..., ge=0)
    price_currency: str = Field(default="UAH", pattern="^UAH$")
    package_grams: int | None = Field(default=None, ge=1)
    strength: int | None = Field(default=None, ge=0, le=10)
    setups_count: int = 0
    is_favorite: bool = False

    model_config = ConfigDict(from_attributes=True)


class TobaccoPageResponse(BaseModel):
    items: list[TobaccoListItem]
    total: int
    limit: int
    offset: int
    has_more: bool

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


class CoalListItem(BaseModel):
    id: UUID4
    name: str
    photo_urls: list[str] = Field(default_factory=list)
    price: int = Field(..., ge=0)
    price_currency: str = Field(default="UAH", pattern="^UAH$")
    coals_per_package: int | None = Field(default=None, ge=1)

    model_config = ConfigDict(from_attributes=True)


class CoalPageResponse(BaseModel):
    items: list[CoalListItem]
    total: int
    limit: int
    offset: int
    has_more: bool

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
    tobacco: TobaccoResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class PublicCreatorResponse(BaseModel):
    id: UUID4
    nickname: str | None = None
    display_name: str
    avatar_url: str | None = None
    role: str = "user"
    badges: list[UserBadge] = Field(default_factory=list)
    setups_count: int = 0
    is_following: bool = False
    last_seen_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BowlSetupBase(BaseModel):
    name: str
    description: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, max_length=8)
    bowl_id: UUID4
    kaloud_id: UUID4
    coal_id: UUID4
    coal_placement_id: UUID4
    bowl_setup_type_id: UUID4

    @field_validator("photo_urls")
    @classmethod
    def validate_photo_urls(cls, value: list[str]):
        for url in value:
            if not is_uploaded_media_url(url):
                raise ValueError("photo_urls must point to uploaded ShishaGuid media")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]):
        normalized = []
        seen = set()
        for tag in value:
            clean = " ".join(tag.strip().lower().split())
            if not clean or clean in seen:
                continue
            if len(clean) > 24:
                raise ValueError("tags must be 24 characters or fewer")
            seen.add(clean)
            normalized.append(clean)
        return normalized[:8]


class BowlSetupCreate(BowlSetupBase):
    tobaccos: list[BowlSetupTobaccoCreate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_tobaccos(self):
        tobacco_ids = [item.tobacco_id for item in self.tobaccos]
        if len(tobacco_ids) != len(set(tobacco_ids)):
            raise ValueError("Setup mix cannot contain duplicate tobaccos")
        percentage_total = sum(item.percentage for item in self.tobaccos)
        if percentage_total != 100:
            raise ValueError("Setup tobacco percentages must sum to 100")
        return self


class BowlSetupResponse(BowlSetupBase):
    id: UUID4
    creator_id: UUID4
    creator: PublicCreatorResponse | None = None
    created_at: datetime
    tags: list[str] = Field(default_factory=list)
    is_featured: bool = False
    views_count: int = 0
    heaviness_score: float | None = None
    average_rating: float = 0
    rating_count: int = 0
    version: int = 1
    source_setup_id: UUID4 | None = None
    is_bookmarked: bool = False
    is_liked: bool = False
    likes_count: int = 0
    comments_count: int = 0
    clones_count: int = 0
    contributors: list[PublicCreatorResponse] = Field(default_factory=list, validation_alias="contributor_users")
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
    replies_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ReviewReplyCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=1000)


class ReviewReplyResponse(BaseModel):
    id: UUID4
    review_id: UUID4
    creator_id: UUID4
    creator: PublicCreatorResponse | None = None
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BowlSetupCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=500)


class BowlSetupCommentResponse(BaseModel):
    id: UUID4
    bowl_setup_id: UUID4
    creator_id: UUID4
    creator: PublicCreatorResponse | None = None
    body: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BowlSetupVersionResponse(BaseModel):
    id: UUID4
    bowl_setup_id: UUID4
    version: int
    snapshot: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContributorCreate(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=80)


class ReportCreate(BaseModel):
    target_type: str = Field(..., pattern="^(setup|review)$")
    target_id: UUID4
    reason: str = Field(..., min_length=3, max_length=1000)


class ReportResponse(BaseModel):
    id: UUID4
    target_type: str
    target_id: UUID4
    reporter_id: UUID4
    reporter: PublicCreatorResponse | None = None
    reason: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
