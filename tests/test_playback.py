import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
from fastapi.testclient import TestClient

from conftest import ALBUM, OTHER_TRACK, SECRET, TRACK, USER
from playback_service.config import Settings
from playback_service.consumer import RabbitConsumer
from playback_service.integrations import Gateway
from playback_service.main import create_app


def make_playback(tmp_path, catalog, *, active=True, mode="ok"):
    catalog_client, _ = catalog
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.host == "catalog-service":
            reply = catalog_client.get(request.url.path)
            return httpx.Response(reply.status_code, json=reply.json())
        assert request.url.host == "subscription-service"
        assert request.url.path == "/api/v1/subscriptions/status"
        assert request.url.params.get("userId") == str(USER)
        header = request.headers["Authorization"]
        token = jwt.decode(header[7:], SECRET, algorithms=["HS256"])
        assert token["sub"] == "playback-service"
        assert token["role"] == "service"
        if mode == "network_error":
            raise httpx.ConnectError("Сервис отключён", request=request)
        if mode == "invalid_response":
            return httpx.Response(200, json={"active": True})
        if mode == "subscription_not_found":
            return httpx.Response(404, json={"error": "NotFound", "message": "Нет подписки"})
        return httpx.Response(200, json={"userId": str(USER), "isActive": active,
                                          "expiresAt": None})

    settings = Settings(database_path=str(tmp_path / "playback.sqlite"),
                        catalog_url="http://catalog-service:8003",
                        subscription_url="http://subscription-service:8004",
                        rabbitmq_url="amqp://unused", jwt_secret_key=SECRET,
                        http_timeout=1, consume_events=False)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = Gateway(settings, client=client)
    app = create_app(settings, gateway)
    return app, client, calls


def test_end_to_end_album_next_pause_resume_stop(tmp_path, catalog, auth_header):
    app, http_client, calls = make_playback(tmp_path, catalog)
    with TestClient(app) as playback:
        playback.app.state.service.start_album(USER, ALBUM)
        response = playback.get("/api/v1/playback/state", headers=auth_header)
        assert response.status_code == 200
        assert response.json() == {
            "status": "playing", "currentTrackId": str(TRACK),
            "albumId": str(ALBUM), "positionSeconds": 0,
        }
        assert playback.post("/api/v1/playback:pause", headers=auth_header).json()["status"] == "paused"
        assert playback.post("/api/v1/playback:resume", headers=auth_header).json()["status"] == "playing"
        next_response = playback.post("/api/v1/playback:next", headers=auth_header)
        assert next_response.status_code == 200
        assert next_response.json()["currentTrackId"] == str(OTHER_TRACK)
        assert playback.post("/api/v1/playback:next", headers=auth_header).status_code == 409
        assert playback.post("/api/v1/playback:stop", headers=auth_header).status_code == 204
        assert playback.get("/api/v1/playback/state", headers=auth_header).json()["status"] == "stopped"
    http_client.close()
    assert any(r.url.path == f"/api/v1/albums/{ALBUM}" for r in calls)
    assert any(r.url.path == f"/api/v1/tracks/{OTHER_TRACK}" for r in calls)
    assert sum(r.url.path.endswith("/subscriptions/status") for r in calls) >= 3


def test_subscription_inactive_does_not_start(tmp_path, catalog, auth_header):
    app, http_client, calls = make_playback(tmp_path, catalog, active=False)
    from playback_service.errors import ApiError
    with TestClient(app) as playback:
        try:
            app.state.service.start_track(USER, TRACK)
            assert False, "Неактивная подписка должна отклоняться"
        except ApiError as error:
            assert error.status_code == 403
        assert playback.get("/api/v1/playback/state", headers=auth_header).json()["status"] == "stopped"
    http_client.close()


def test_subscription_network_error_does_not_start(tmp_path, catalog, auth_header):
    app, http_client, calls = make_playback(tmp_path, catalog, mode="network_error")
    from playback_service.errors import ApiError
    with TestClient(app) as playback:
        try:
            app.state.service.start_track(USER, TRACK)
            assert False
        except ApiError as error:
            assert error.status_code == 503
        assert playback.get("/api/v1/playback/state", headers=auth_header).json()["status"] == "stopped"
    http_client.close()


def test_bad_subscription_contract_returns_502(tmp_path, catalog):
    app, http_client, calls = make_playback(tmp_path, catalog, mode="invalid_response")
    from playback_service.errors import ApiError
    with TestClient(app):
        try:
            app.state.service.start_track(USER, TRACK)
            assert False
        except ApiError as error:
            assert error.status_code == 502
    http_client.close()


def test_missing_track_returns_404(tmp_path, catalog):
    app, http_client, calls = make_playback(tmp_path, catalog)
    from playback_service.errors import ApiError
    with TestClient(app):
        try:
            app.state.service.start_track(USER, uuid4())
            assert False
        except ApiError as error:
            assert error.status_code == 404
    http_client.close()
    assert not any(r.url.host == "subscription-service" for r in calls)


def test_seek_previous_and_queue_management(tmp_path, catalog, auth_header):
    app, http_client, calls = make_playback(tmp_path, catalog)
    with TestClient(app) as playback:
        playback.app.state.service.start_album(USER, ALBUM)

        # 1. Seek
        seek_res = playback.post("/api/v1/playback:seek", json={"positionSeconds": 45}, headers=auth_header)
        assert seek_res.status_code == 200
        assert seek_res.json()["positionSeconds"] == 45

        # 2. Next & Previous
        playback.post("/api/v1/playback:next", headers=auth_header)
        assert playback.get("/api/v1/playback/state", headers=auth_header).json()["currentTrackId"] == str(OTHER_TRACK)

        prev_res = playback.post("/api/v1/playback:previous", headers=auth_header)
        assert prev_res.status_code == 200
        assert prev_res.json()["currentTrackId"] == str(TRACK)

        # 3. Queue management
        queue_res = playback.get("/api/v1/playback/queue", headers=auth_header)
        assert queue_res.status_code == 200
        assert len(queue_res.json()["items"]) == 2

        add_res = playback.post("/api/v1/playback/queue", json={"trackId": str(TRACK)}, headers=auth_header)
        assert add_res.status_code == 201
        added_id = add_res.json()["id"]

        del_res = playback.delete(f"/api/v1/playback/queue/{added_id}", headers=auth_header)
        assert del_res.status_code == 204
    http_client.close()


def test_jwt_required_and_route_limit(tmp_path, catalog, auth_header):
    app, http_client, _ = make_playback(tmp_path, catalog)
    with TestClient(app) as playback:
        assert playback.get("/api/v1/playback/state").status_code == 401
        assert playback.get("/api/v1/playback/state", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert playback.get("/api/v1/playback/state", headers=auth_header).status_code == 200
        assert playback.post("/api/v1/playback:pause", headers=auth_header).status_code == 409
        paths = [r.path for r in playback.app.routes if r.path.startswith("/api/v1/")]
        assert len(paths) == 10
    http_client.close()


def test_rabbitmq_event_handler_and_idempotency(tmp_path, catalog, auth_header):
    app, http_client, _ = make_playback(tmp_path, catalog)
    with TestClient(app) as playback:
        consumer = RabbitConsumer(app.state.gateway.settings, app.state.service)
        acknowledgements = []

        class FakeChannel:
            def basic_ack(self, delivery_tag):
                acknowledgements.append(("ack", delivery_tag))
            def basic_nack(self, delivery_tag, requeue):
                acknowledgements.append(("nack", delivery_tag, requeue))

        payload = {"eventId": str(uuid4()), "event": "TrackSelected",
                   "userId": str(USER), "trackId": str(TRACK)}
        method = SimpleNamespace(delivery_tag=7)
        consumer._handle_message(FakeChannel(), method, None, json.dumps(payload).encode())
        assert acknowledgements == [("ack", 7)]
        assert playback.get("/api/v1/playback/state", headers=auth_header).json()["status"] == "playing"
        playback.post("/api/v1/playback:stop", headers=auth_header)
        consumer._handle_message(FakeChannel(), method, None, json.dumps(payload).encode())
        assert playback.get("/api/v1/playback/state", headers=auth_header).json()["status"] == "stopped"
    http_client.close()
