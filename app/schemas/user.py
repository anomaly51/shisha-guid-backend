from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field, field_validator

ROLE_PATTERN = r"^[a-z][a-z0-9_]{0,31}$"
BADGE_EFFECT_PATTERN = r"^(none|frost|fire|chemical|electric|cosmic|shimmer)$"
BADGE_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"


class UserRoleUpdate(BaseModel):
    role: str = Field(..., pattern=ROLE_PATTERN)


class UserBanUpdate(BaseModel):
    is_banned: bool


class AdminUserUpdate(BaseModel):
    nickname: str | None = Field(default=None, max_length=40)
    avatar_url: str | None = None
    role: str | None = Field(default=None, pattern=ROLE_PATTERN)
    is_banned: bool | None = None
    badge_label: str | None = Field(default=None, max_length=28)
    badge_color: str | None = Field(default=None, pattern=BADGE_COLOR_PATTERN)
    badge_effect: str | None = Field(default="none", pattern=BADGE_EFFECT_PATTERN)
    badges: list[str] | None = Field(default=None, max_length=1)

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str | None):
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class UserBadge(BaseModel):
    label: str
    color: str
    effect: str = "none"


class UserProfileResponse(BaseModel):
    id: UUID4
    email: str
    nickname: str | None
    google_id: str
    avatar_url: str | None = None
    role: str = "user"
    is_banned: bool = False
    badges: list[UserBadge] = Field(default_factory=list)
    last_seen_at: datetime | None = None
    last_active_at: datetime | None = None
    streak_days: int = 0
    score: int = 0

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    nickname: str | None = None
    avatar_url: str | None = None

    @field_validator("nickname")
    @classmethod
    def normalize_nickname(cls, value: str | None):
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            return None
        if len(normalized) > 40:
            raise ValueError("Nickname must be 40 characters or fewer")
        return normalized


class AdminUserResponse(UserProfileResponse):
    pass


class PublicUserResponse(BaseModel):
    id: UUID4
    nickname: str | None = None
    display_name: str
    avatar_url: str | None = None
    role: str = "user"
    badges: list[UserBadge] = Field(default_factory=list)
    setups_count: int = 0
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False
    is_followed_by: bool = False
    last_seen_at: datetime | None = None
    last_active_at: datetime | None = None
    streak_days: int = 0
    score: int = 0

    model_config = ConfigDict(from_attributes=True)


class UserActivityResponse(BaseModel):
    id: str
    type: str
    title: str
    setup_id: UUID4 | None = None
    created_at: datetime


class NotificationResponse(BaseModel):
    id: UUID4
    type: str
    title: str
    body: str | None = None
    actor_id: UUID4 | None = None
    bowl_setup_id: UUID4 | None = None
    read_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationPageResponse(BaseModel):
    items: list[NotificationResponse]
    unread_count: int


class SetupCollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str):
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Collection name is required")
        return normalized


class SetupCollectionResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    name: str
    created_at: datetime
    setup_ids: list[UUID4] = Field(default_factory=list)
    items_count: int = 0

    model_config = ConfigDict(from_attributes=True)
