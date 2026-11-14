import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import jwt
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "catalog-service"))
sys.path.insert(0, str(ROOT / "playback-service"))
sys.path.insert(0, str(ROOT / "playlists-service"))
sys.path.insert(0, str(ROOT / "subscription-service"))

USER = UUID("770e8400-e29b-41d4-a716-446655440000")
TRACK = UUID("550e8400-e29b-41d4-a716-446655440000")
OTHER_TRACK = UUID("660e8400-e29b-41d4-a716-446655440003")
ALBUM = UUID("770e8400-e29b-41d4-a716-446655440002")
SECRET = "test-not-for-production-unique-long-secret-32"


@pytest.fixture
def auth_header():
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(USER), "iat": now, "exp": now + timedelta(minutes=10)},
                       SECRET, algorithm="HS256")
    return {"Authorization": "Bearer " + token}


class FakePublisher:
    def __init__(self):
        self.events = []

    def publish(self, event, routing_key):
        self.events.append((event, routing_key))


@pytest.fixture
def catalog(tmp_path):
    from fastapi.testclient import TestClient
    from catalog_service.config import Settings
    from catalog_service.main import create_app

    publisher = FakePublisher()
    app = create_app(
        Settings(database_path=str(tmp_path / "catalog.sqlite"),
                 rabbitmq_url="amqp://unused", jwt_secret_key=SECRET),
        publisher=publisher,
    )
    with TestClient(app) as client:
        yield client, publisher
