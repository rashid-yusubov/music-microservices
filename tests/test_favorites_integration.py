import sys
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient
import pytest

from conftest import SECRET, TRACK, USER
from playlists_service.config import Settings as PlaylistsSettings
from playlists_service.integrations import CatalogGateway
from playlists_service.main import create_app as create_playlists_app

SEED_PLAYLIST = UUID("660e8400-e29b-41d4-a716-446655440000")


def test_favorites_integration_with_playlists_and_catalog(tmp_path, auth_header, monkeypatch):
    # Добавляем путь к favorites-service
    fav_root = Path(__file__).resolve().parents[1] / "favorites-service"
    if str(fav_root) not in sys.path:
        sys.path.insert(0, str(fav_root))

    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)

    from clients import external_client as ext_module
    from security import auth as auth_module
    from main import app as favorites_app

    monkeypatch.setattr(auth_module, "SECRET_KEY", SECRET)

    # Создаём реальное приложение Playlists Service
    pl_settings = PlaylistsSettings(
        database_path=str(tmp_path / "playlists.sqlite"),
        jwt_secret_key=SECRET,
    )
    playlists_app = create_playlists_app(pl_settings)

    # Клиент тестирования для favorites
    with TestClient(playlists_app) as playlists_client, TestClient(favorites_app) as favorites_client:

        # Перехватываем вызовы external_client и маршрутизируем в наш настоящий Playlists Service
        def mock_playlist_exists(playlist_id: str) -> bool:
            resp = playlists_client.get(f"/api/v1/playlists/{playlist_id}")
            return resp.status_code == 200

        def mock_track_exists(track_id: str) -> bool:
            return str(track_id) == str(TRACK)

        monkeypatch.setattr(ext_module.external_client, "playlist_exists", mock_playlist_exists)
        monkeypatch.setattr(ext_module.external_client, "track_exists", mock_track_exists)

        # 1. Добавление тестового seed-плейлиста в избранное (успешно, 204)
        add_pl = favorites_client.put(
            f"/api/v1/favorites/playlists/{SEED_PLAYLIST}",
            headers=auth_header,
        )
        assert add_pl.status_code == 204

        # 2. Попытка добавить несуществующий плейлист (404)
        missing_pl = favorites_client.put(
            f"/api/v1/favorites/playlists/{uuid4()}",
            headers=auth_header,
        )
        assert missing_pl.status_code == 404

        # 3. Добавление существующего трека в избранное (успешно, 204)
        add_tr = favorites_client.put(
            f"/api/v1/favorites/tracks/{TRACK}",
            headers=auth_header,
        )
        assert add_tr.status_code == 204

        # 4. Попытка добавить отсутствующий трек (404)
        missing_tr = favorites_client.put(
            f"/api/v1/favorites/tracks/{uuid4()}",
            headers=auth_header,
        )
        assert missing_tr.status_code == 404

        # 5. Удаление трека из избранного (204)
        del_tr = favorites_client.delete(
            f"/api/v1/favorites/tracks/{TRACK}",
            headers=auth_header,
        )
        assert del_tr.status_code == 204

        # 6. Удаление плейлиста из избранного (204)
        del_pl = favorites_client.delete(
            f"/api/v1/favorites/playlists/{SEED_PLAYLIST}",
            headers=auth_header,
        )
        assert del_pl.status_code == 204


def test_favorites_repository_sqlite_persistence(tmp_path):
    fav_root = Path(__file__).resolve().parents[1] / "favorites-service"
    if str(fav_root) not in sys.path:
        sys.path.insert(0, str(fav_root))

    from repositories.favorite_repository import FavoriteRepository
    from models.favorite import Favorite

    db_path = str(tmp_path / "test_fav.sqlite3")
    repo = FavoriteRepository(db_path=db_path)

    u_id = uuid4()
    item1 = uuid4()
    item2 = uuid4()

    assert not repo.exists(u_id, item1, "track")

    repo.add(Favorite(user_id=u_id, item_id=item1, item_type="track"))
    repo.add(Favorite(user_id=u_id, item_id=item2, item_type="playlist"))

    assert repo.exists(u_id, item1, "track")
    assert repo.exists(u_id, item2, "playlist")

    # Пересоздаем репозиторий с тем же файлом БД для проверки персистентности
    repo2 = FavoriteRepository(db_path=db_path)
    assert repo2.exists(u_id, item1, "track")
    assert repo2.exists(u_id, item2, "playlist")

    items = repo2.list_by_user(u_id)
    assert len(items) == 2

    repo2.remove(u_id, item1, "track")
    assert not repo2.exists(u_id, item1, "track")
    assert repo2.exists(u_id, item2, "playlist")
