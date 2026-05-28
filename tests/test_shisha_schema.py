import uuid
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test")

from app.schemas.shisha import BowlSetupCreate


def _setup_payload(percentages: list[int]) -> dict:
    return {
        "name": "Test setup",
        "description": None,
        "photo_urls": [],
        "tags": [],
        "bowl_id": uuid.uuid4(),
        "kaloud_id": uuid.uuid4(),
        "coal_id": uuid.uuid4(),
        "coal_placement_id": uuid.uuid4(),
        "bowl_setup_type_id": uuid.uuid4(),
        "tobaccos": [
            {"tobacco_id": uuid.uuid4(), "percentage": percentage}
            for percentage in percentages
        ],
    }


def test_bowl_setup_percentages_must_sum_to_100():
    with pytest.raises(ValueError, match="percentages must sum to 100"):
        BowlSetupCreate(**_setup_payload([40, 40]))


def test_bowl_setup_accepts_percentages_equal_to_100():
    schema = BowlSetupCreate(**_setup_payload([40, 60]))

    assert sum(item.percentage for item in schema.tobaccos) == 100
