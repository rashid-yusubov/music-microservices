from uuid import uuid4

from conftest import ALBUM, TRACK, USER


def test_track_contract_for_favorites(catalog):
    client, _ = catalog
    response = client.get(f"/api/v1/tracks/{TRACK}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(TRACK)
    assert data["title"] == "Example Track"
    assert data["artist"] == "Example Artist"
    assert data["status"] == "approved"
    assert data["durationSeconds"] == 215
    assert data["albumId"] == str(ALBUM)


def test_missing_and_invalid_track(catalog):
    client, _ = catalog
    missing = client.get(f"/api/v1/tracks/{uuid4()}")
    assert missing.status_code == 404
    assert set(missing.json()) == {"error", "message"}
    malformed = client.get("/api/v1/tracks/not-a-uuid")
    assert malformed.status_code == 400


def test_search_pagination_and_album(catalog):
    client, _ = catalog
    page = client.get("/api/v1/tracks", params={"query": "Example", "offset": 0, "count": 1})
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert len(page.json()["items"]) == 1
    assert client.get("/api/v1/tracks", params={"count": 101}).status_code == 400
    album = client.get(f"/api/v1/albums/{ALBUM}")
    assert album.status_code == 200
    assert album.json()["trackIds"][0] == str(TRACK)


def test_select_publishes_events(catalog, auth_header):
    client, publisher = catalog
    track = client.post(f"/api/v1/tracks/{TRACK}:select", headers=auth_header)
    assert track.status_code == 202
    assert track.json()["event"] == "TrackSelected"
    assert publisher.events[0][1] == "track.selected"
    assert publisher.events[0][0]["userId"] == str(USER)
    assert publisher.events[0][0]["trackId"] == str(TRACK)
    album = client.post(f"/api/v1/albums/{ALBUM}:select", headers=auth_header)
    assert album.status_code == 202
    assert publisher.events[1][1] == "album.selected"
    assert publisher.events[1][0]["albumId"] == str(ALBUM)
    assert client.post(f"/api/v1/tracks/{TRACK}:select").status_code == 401


def test_albums_search(catalog):
    client, _ = catalog
    res = client.get("/api/v1/albums", params={"query": "Example"})
    assert res.status_code == 200
    assert res.json()["total"] >= 1
    assert res.json()["items"][0]["id"] == str(ALBUM)


def test_track_moderation_and_lifecycle(catalog, auth_header):
    client, _ = catalog
    # 1. Загрузка/регистрация нового трека (pending)
    new_track_body = {
        "title": "New Uploaded Track",
        "artist": "Example Artist",
        "albumId": str(ALBUM),
        "mediaId": str(uuid4()),
        "durationSeconds": 180,
    }
    create_res = client.post("/api/v1/tracks", json=new_track_body, headers=auth_header)
    assert create_res.status_code == 201
    track_id = create_res.json()["id"]
    assert create_res.json()["status"] == "pending"

    # Неопубликованный трек не отдается в GET /tracks/{track_id}
    assert client.get(f"/api/v1/tracks/{track_id}").status_code == 404

    # 2. Одобрение трека модератором
    approve_res = client.post(f"/api/v1/tracks/{track_id}:approve", headers=auth_header)
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # Теперь трек доступен
    assert client.get(f"/api/v1/tracks/{track_id}").status_code == 200

    # 3. Редактирование метаданных (снова переводит в pending)
    patch_res = client.patch(f"/api/v1/tracks/{track_id}", json={"title": "Updated Title"}, headers=auth_header)
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated Title"
    assert patch_res.json()["status"] == "pending"

    # 4. Отклонение трека
    reject_res = client.post(
        f"/api/v1/tracks/{track_id}:reject",
        json={"reason": "Плохое качество"},
        headers=auth_header,
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "rejected"
    assert reject_res.json()["reason"] == "Плохое качество"


def test_route_limit(catalog):
    client, _ = catalog
    paths = [r.path for r in client.app.routes if r.path.startswith("/api/v1/")]
    assert len(paths) == 10
