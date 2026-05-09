from pydantic import BaseModel


class GoogleTokenRequest(BaseModel):
    code: str
    client_id: str
    redirect_uri: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
