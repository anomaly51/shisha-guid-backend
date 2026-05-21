from typing import Literal

from pydantic import BaseModel, Field


class AgentChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class AgentDraftTobacco(BaseModel):
    tobacco_id: str | None = None
    tobacco_name: str | None = None
    percentage: int | None = Field(default=None, ge=1, le=100)


class AgentSetupDraft(BaseModel):
    name: str | None = None
    description: str | None = None
    bowl_id: str | None = None
    bowl_name: str | None = None
    kaloud_id: str | None = None
    kaloud_name: str | None = None
    coal_id: str | None = None
    coal_name: str | None = None
    coal_placement_id: str | None = None
    coal_placement_name: str | None = None
    bowl_setup_type_id: str | None = None
    bowl_setup_type_name: str | None = None
    tobaccos: list[AgentDraftTobacco] = Field(default_factory=list)


class AgentChatRequest(BaseModel):
    messages: list[AgentChatMessage] = Field(..., min_length=1, max_length=20)
    draft: AgentSetupDraft | None = None
    publish: bool = False


class AgentChatResponse(BaseModel):
    reply: str
    draft: AgentSetupDraft | None = None
    needs_confirmation: bool = False
    created_setup_id: str | None = None


class AgentTranscribeResponse(BaseModel):
    text: str
