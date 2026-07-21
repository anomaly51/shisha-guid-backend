import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")

import jwt

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token


def _decode(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def test_access_token_contains_explicit_type():
    payload = _decode(create_access_token({"sub": "user-id"}))

    assert payload["typ"] == "access"


def test_refresh_token_contains_explicit_type():
    payload = _decode(create_refresh_token({"sub": "user-id"}))

    assert payload["typ"] == "refresh"
