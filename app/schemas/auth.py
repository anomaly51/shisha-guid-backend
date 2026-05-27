from pydantic import BaseModel


class GoogleTokenRequest(BaseModel):
    code: str
    client_id: str
    redirect_uri: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class TokenRefreshRequest(BaseModel):
    refresh_token: str
