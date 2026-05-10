from pydantic import BaseModel


class UploadPolicyResponse(BaseModel):
    url: str
    form_data: dict
