from datetime import datetime, timezone
from uuid import UUID, uuid4

from .errors import ApiError
from .integrations import CatalogGateway
from .models import (
    CoverResponse,
    Playlist,
    PlaylistCreate,
    PlaylistPage,
    RenameResponse,
    ReorderResponse,
)
from .repository import PlaylistRepository


class PlaylistService:
    def __init__(self, repository: PlaylistRepository, catalog_gateway: CatalogGateway):
        self.repository = repository
        self.catalog_gateway = catalog_gateway

    def get_playlist(self, playlist_id: UUID) -> Playlist:
        playlist = self.repository.get_playlist(playlist_id)
        if not playlist:
            raise ApiError(404, "NotFound", "Плейлист не найден")
        return playlist

    def list_playlists(
        self,
        query: str | None = None,
        owner_id: UUID | None = None,
        offset: int = 0,
        count: int = 20,
    ) -> PlaylistPage:
        items, total = self.repository.list_playlists(query, owner_id, offset, count)
        return PlaylistPage(items=items, offset=offset, count=count, total=total)

    def create_playlist(self, data: PlaylistCreate, owner_id: UUID) -> Playlist:
        playlist_id = uuid4()
        created_at = datetime.now(timezone.utc).isoformat()
        return self.repository.create_playlist(
            playlist_id=playlist_id,
            name=data.name,
            description=data.description,
            owner_id=owner_id,
            cover_url=data.coverUrl,
            created_at=created_at,
        )

    def add_track(self, playlist_id: UUID, track_id: UUID, user_id: UUID) -> Playlist:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        # Синхронная проверка существования трека через Music Catalog
        self.catalog_gateway.get_track(track_id)

        self.repository.add_track(playlist_id, track_id)
        return self.get_playlist(playlist_id)

    def remove_track(self, playlist_id: UUID, track_id: UUID, user_id: UUID) -> None:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        if track_id not in playlist.trackIds:
            raise ApiError(404, "NotFound", "Трек не найден в плейлисте")

        self.repository.remove_track(playlist_id, track_id)

    def reorder_tracks(self, playlist_id: UUID, track_ids: list[UUID], user_id: UUID) -> ReorderResponse:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        if set(track_ids) != set(playlist.trackIds) or len(track_ids) != len(playlist.trackIds):
            raise ApiError(400, "BadRequest", "Некорректный список идентификаторов треков")

        self.repository.reorder_tracks(playlist_id, track_ids)
        return ReorderResponse(playlistId=playlist_id, trackIds=track_ids)

    def rename_playlist(self, playlist_id: UUID, name: str, user_id: UUID) -> RenameResponse:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        self.repository.rename_playlist(playlist_id, name)
        return RenameResponse(id=playlist_id, name=name, ownerId=user_id)

    def update_cover(self, playlist_id: UUID, cover_url: str, user_id: UUID) -> CoverResponse:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        self.repository.update_cover(playlist_id, cover_url)
        return CoverResponse(playlistId=playlist_id, coverUrl=cover_url)

    def pin_playlist(self, playlist_id: UUID, user_id: UUID) -> None:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        self.repository.set_pinned(playlist_id, True)

    def unpin_playlist(self, playlist_id: UUID, user_id: UUID) -> None:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        self.repository.set_pinned(playlist_id, False)

    def delete_playlist(self, playlist_id: UUID, user_id: UUID) -> None:
        playlist = self.get_playlist(playlist_id)
        if playlist.ownerId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для изменения данного плейлиста")

        self.repository.delete_playlist(playlist_id)
