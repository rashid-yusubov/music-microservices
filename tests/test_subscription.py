from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from fastapi.testclient import TestClient

from conftest import SECRET, USER
from subscription_service.config import Settings
from subscription_service.main import create_app

SEED_SUBSCRIPTION_ID = UUID("880e8400-e29b-41d4-a716-446655440000")


def make_subscription_service(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "subscription.sqlite"),
        jwt_secret_key=SECRET,
    )
    return create_app(settings)


def test_seed_subscription_contract_for_playback(tmp_path):
    app = make_subscription_service(tmp_path)
    now = datetime.now(timezone.utc)
    service_token = jwt.encode(
        {"sub": "playback-service", "role": "service", "iat": now, "exp": now + timedelta(minutes=5)},
        SECRET,
        algorithm="HS256",
    )
    with TestClient(app) as client:
        # 1. Запрос от Playback Service со служебным токеном
        res = client.get(
            "/api/v1/subscriptions/status",
            params={"userId": str(USER)},
            headers={"Authorization": f"Bearer {service_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["userId"] == str(USER)
        assert data["isActive"] is True
        assert data["expiresAt"] is not None

        # 2. Несуществующий пользователь - возвращает isActive=False
        unknown_user = uuid4()
        res_unknown = client.get(
            "/api/v1/subscriptions/status",
            params={"userId": str(unknown_user)},
            headers={"Authorization": f"Bearer {service_token}"},
        )
        assert res_unknown.status_code == 200
        assert res_unknown.json()["userId"] == str(unknown_user)
        assert res_unknown.json()["isActive"] is False
        assert res_unknown.json()["expiresAt"] is None

        # 3. Некорректный UUID - 400
        res_invalid = client.get(
            "/api/v1/subscriptions/status",
            params={"userId": "not-a-uuid"},
            headers={"Authorization": f"Bearer {service_token}"},
        )
        assert res_invalid.status_code == 400


def test_user_subscription_lifecycle(tmp_path, auth_header):
    app = make_subscription_service(tmp_path)
    with TestClient(app) as client:
        # Просмотр существующей подписки (seed подписка для USER)
        my_sub = client.get("/api/v1/subscriptions/my", headers=auth_header)
        assert my_sub.status_code == 200
        assert my_sub.json()["userId"] == str(USER)
        assert my_sub.json()["isActive"] is True

        # Отмена подписки
        cancel_res = client.post("/api/v1/subscriptions/cancel", headers=auth_header)
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"
        assert cancel_res.json()["isActive"] is False

        # Проверка статуса после отмены
        status_res = client.get("/api/v1/subscriptions/status", params={"userId": str(USER)})
        assert status_res.status_code == 200
        assert status_res.json()["isActive"] is False

        # Оформление новой подписки
        new_sub = client.post(
            "/api/v1/subscriptions",
            json={"plan": "premium", "durationDays": 60},
            headers=auth_header,
        )
        assert new_sub.status_code == 201
        assert new_sub.json()["plan"] == "premium"
        assert new_sub.json()["isActive"] is True

        # Проверка статуса после переоформления
        status_res2 = client.get("/api/v1/subscriptions/status", params={"userId": str(USER)})
        assert status_res2.status_code == 200
        assert status_res2.json()["isActive"] is True


def test_subscription_renew_complete_cancel_by_id(tmp_path, auth_header):
    app = make_subscription_service(tmp_path)
    now = datetime.now(timezone.utc)
    service_token = jwt.encode(
        {"sub": "system", "role": "service", "iat": now, "exp": now + timedelta(minutes=5)},
        SECRET,
        algorithm="HS256",
    )
    with TestClient(app) as client:
        # 1. Продление
        renew_res = client.post(
            f"/api/v1/subscriptions/{SEED_SUBSCRIPTION_ID}/renew",
            headers=auth_header,
        )
        assert renew_res.status_code == 200
        assert renew_res.json()["status"] == "active"

        # 2. Отмена по ID
        cancel_res = client.post(
            f"/api/v1/subscriptions/{SEED_SUBSCRIPTION_ID}/cancel",
            headers=auth_header,
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # 3. Завершение системным сервисом
        complete_res = client.post(
            f"/api/v1/subscriptions/{SEED_SUBSCRIPTION_ID}/complete",
            headers={"Authorization": f"Bearer {service_token}"},
        )
        assert complete_res.status_code == 200
        assert complete_res.json()["status"] == "completed"


def test_subscription_route_limit(tmp_path):
    app = make_subscription_service(tmp_path)
    with TestClient(app) as client:
        paths = [r.path for r in client.app.routes if r.path.startswith("/api/v1/")]
        assert len(paths) == 7
