from pydantic import UUID4, BaseModel


class UserProfileResponse(BaseModel):
    id: UUID4
    email: str
    nickname: str | None
    google_id: str


class UserProfileUpdate(BaseModel):
    nickname: str
