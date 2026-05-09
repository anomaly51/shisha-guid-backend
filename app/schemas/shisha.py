from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field


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


class TobaccoCreate(ComponentCreate):
    pass


class TobaccoResponse(ComponentResponse):
    pass


class CoalCreate(ComponentCreate):
    pass


class CoalResponse(ComponentResponse):
    pass


class KaloudCreate(ComponentCreate):
    pass


class KaloudResponse(ComponentResponse):
    pass


class BowlCreate(ComponentCreate):
    pass


class BowlResponse(ComponentResponse):
    pass


class CoalPlacementCreate(ComponentCreate):
    pass


class CoalPlacementResponse(ComponentResponse):
    pass


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


class BowlSetupBase(BaseModel):
    name: str
    description: str | None = None
    photo_urls: list[str] = Field(default_factory=list)
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
    created_at: datetime
    tobaccos: list[BowlSetupTobaccoResponse]

    model_config = ConfigDict(from_attributes=True)
