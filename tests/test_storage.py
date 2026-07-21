import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")

from app.core.config import settings
from app.core.storage import detect_image_content_type, is_uploaded_media_url


def test_detect_image_content_type_handles_short_content():
    assert detect_image_content_type(b"RIFF") is None
    assert detect_image_content_type(b"") is None


def test_uploaded_media_url_rejects_external_api_like_host(monkeypatch):
    monkeypatch.setattr(settings, "API_PUBLIC_URL", "https://api.example.test")

    assert is_uploaded_media_url("https://api.example.test/api/v1/upload/media/u/file.jpg")
    assert not is_uploaded_media_url("https://evil.example/api/v1/upload/media/u/file.jpg")
