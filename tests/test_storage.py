import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")

from app.core.storage import detect_image_content_type


def test_detect_image_content_type_handles_short_content():
    assert detect_image_content_type(b"RIFF") is None
    assert detect_image_content_type(b"") is None
