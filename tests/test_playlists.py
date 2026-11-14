from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient

from conftest import SECRET, TRACK, USER
from playlists_service.config import Settings
from playlists_service.integrations import CatalogGateway
from playlists_service.main import create_app

SEED_PLAYLIST = UUID("660e8400-e29b-41d4-a716-446655440000")


def make_playlists_service(tmp_path, *, catalog_mode="ok"):
    calls = []

    def catalog_handler(request):
        calls.append(request)
        if catalog_mode == "network_error":
            raise httpx.ConnectError("Каталог недоступен", request=request)
        if catalog_mode == "catalog_not_found":
            return httpx.Response(404, json={"error": "NotFound", "message": "Трек отсутствует в каталоге"})
        if catalog_mode == "invalid_json":
            return httpx.Response(200, text="non-json")
        if catalog_mode == "bad_contract":
            return httpx.Response(200, json={"something": "wrong"})
        # Default ok: return track info
        return httpx.Response(
            200,
            json={
                "id": str(TRACK),
                "title": "Example Track",
                "artist": "Example Artist",
                "albumId": "770e8400-e29b-41d4-a716-446655440002",
                "durationSeconds": 215,
                "status": "approved",
            },
        )

    settings = Settings(
        database_path=str(tmp_path / "playlists.sqlite"),
        catalog_url="http://catalog-service:8003",
        jwt_secret_key=SECRET,
        http_timeout=1.0,
    )
    http_client = httpx.Client(transport=httpx.MockTransport(catalog_handler))
    gateway = CatalogGateway(settings, client=http_client)
    app = create_app(settings, catalog_gateway=gateway)
    return app, http_client, calls


def test_seed_playlist_contract_for_favorites(tmp_path):
    app, http_client, _ = make_playlists_service(tmp_path)
    with TestClient(app) as client:
        response = client.get(f"/api/v1/playlists/{SEED_PLAYLIST}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(SEED_PLAYLIST)
        assert data["name"] == "My Playlist"
        assert data["ownerId"] == str(USER)
        assert str(TRACK) in data["trackIds"]
    http_client.close()


def test_missing_and_invalid_playlist(tmp_path):
    app, http_client, _ = make_playlists_service(tmp_path)
    with TestClient(app) as client:
        missing = client.get(f"/api/v1/playlists/{uuid4()}")
        assert missing.status_code == 404
        assert set(missing.json()) == {"error", "message"}

        malformed = client.get("/api/v1/playlists/invalid-uuid")
        assert malformed.status_code == 400
        assert set(malformed.json()) == {"error", "message"}
    http_client.close()


def test_create_and_list_playlists(tmp_path, auth_header):
    app, http_client, _ = make_playlists_service(tmp_path)
    with TestClient(app) as client:
        unauthorized = client.post("/api/v1/playlists", json={"name": "New Playlist"})
        assert unauthorized.status_code == 401

        created = client.post(
            "/api/v1/playlists",
            json={"name": "New Playlist", "description": "Chill vibes"},
            headers=auth_header,
        )
        assert created.status_code == 201
        new_id = created.json()["id"]
        assert created.json()["name"] == "New Playlist"
        assert created.json()["ownerId"] == str(USER)

        page = client.get("/api/v1/playlists", params={"query": "New"})
        assert page.status_code == 200
        assert page.json()["total"] == 1
        assert page.json()["items"][0]["id"] == new_id
    http_client.close()


def test_sync_track_validation_via_catalog(tmp_path, auth_header):
    app, http_client, calls = make_playlists_service(tmp_path, catalog_mode="ok")
    with TestClient(app) as client:
        add_res = client.post(
            f"/api/v1/playlists/{SEED_PLAYLIST}/tracks",
            json={"trackId": str(TRACK)},
            headers=auth_header,
        )
        assert add_res.status_code == 200
        assert str(TRACK) in add_res.json()["trackIds"]
        assert any(r.url.path == f"/api/v1/tracks/{TRACK}" for r in calls)
    http_client.close()

    app_not_found, client_nf, _ = make_playlists_service(tmp_path, catalog_mode="catalog_not_found")
    with TestClient(app_not_found) as client:
        res = client.post(
            f"/api/v1/playlists/{SEED_PLAYLIST}/tracks",
            json={"trackId": str(uuid4())},
            headers=auth_header,
        )
        assert res.status_code == 404
        assert res.json()["message"] == "Трек отсутствует в каталоге"
    client_nf.close()

    app_net_err, client_ne, _ = make_playlists_service(tmp_path, catalog_mode="network_error")
    with TestClient(app_net_err) as client:
        res = client.post(
            f"/api/v1/playlists/{SEED_PLAYLIST}/tracks",
            json={"trackId": str(TRACK)},
            headers=auth_header,
        )
        assert res.status_code == 503
        assert res.json()["message"] == "Каталог недоступен"
    client_ne.close()


def test_remove_track_from_playlist(tmp_path, auth_header):
    app, http_client, _ = make_playlists_service(tmp_path)
    with TestClient(app) as client:
        del_res = client.delete(
            f"/api/v1/playlists/{SEED_PLAYLIST}/tracks/{TRACK}",
            headers=auth_header,
        )
        assert del_res.status_code == 204

        del_res2 = client.delete(
            f"/api/v1/playlists/{SEED_PLAYLIST}/tracks/{TRACK}",
            headers=auth_header,
        )
        assert del_res2.status_code == 404
    http_client.close()


def test_playlist_extended_management(tmp_path, auth_header):
    app, http_client, _ = make_playlists_service(tmp_path)
    with TestClient(app) as client:
        # 1. Rename
        rename_res = client.patch(
            f"/api/v1/playlists/{SEED_PLAYLIST}",
            json={"name": "Renamed Playlist"},
            headers=auth_header,
        )
        assert rename_res.status_code == 200
        assert rename_res.json()["name"] == "Renamed Playlist"

        # 2. Cover
        cover_res = client.put(
            f"/api/v1/playlists/{SEED_PLAYLIST}/cover",
            json={"coverUrl": "https://example.com/cover.jpg"},
            headers=auth_header,
        )
        assert cover_res.status_code == 200
        assert cover_res.json()["coverUrl"] == "https://example.com/cover.jpg"

        # 3. Pin & Unpin
        assert client.put(f"/api/v1/playlists/{SEED_PLAYLIST}/pin", headers=auth_header).status_code == 204
        assert client.get(f"/api/v1/playlists/{SEED_PLAYLIST}").json()["isPinned"] is True

        assert client.delete(f"/api/v1/playlists/{SEED_PLAYLIST}/pin", headers=auth_header).status_code == 204
        assert client.get(f"/api/v1/playlists/{SEED_PLAYLIST}").json()["isPinned"] is False

        # 4. Reorder tracks
        order_res = client.patch(
            f"/api/v1/playlists/{SEED_PLAYLIST}/tracks/order",
            json={"trackIds": [str(TRACK)]},
            headers=auth_header,
        )
        assert order_res.status_code == 200

        # 5. Delete playlist
        assert client.delete(f"/api/v1/playlists/{SEED_PLAYLIST}", headers=auth_header).status_code == 204
        assert client.get(f"/api/v1/playlists/{SEED_PLAYLIST}").status_code == 404
    http_client.close()


def test_playlists_route_limit(tmp_path):
    app, http_client, _ = make_playlists_service(tmp_path)
    with TestClient(app) as client:
        paths = [r.path for r in client.app.routes if r.path.startswith("/api/v1/")]
        assert len(paths) == 11
    http_client.close()
