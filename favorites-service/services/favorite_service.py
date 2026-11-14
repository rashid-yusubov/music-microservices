from uuid import UUID

from models.favorite import Favorite
from repositories.favorite_repository import favorite_repository
from clients.external_client import external_client


class FavoriteService:

    def add_track(self, user_id: UUID, track_id: UUID) -> None:
        # Проверяем существование трека в музыкальном каталоге
        if not external_client.track_exists(str(track_id)):
            raise ValueError("Track not found")

        favorite = Favorite(
            user_id=user_id,
            item_id=track_id,
            item_type="track"
        )

        favorite_repository.add(favorite)

    def remove_track(self, user_id: UUID, track_id: UUID) -> None:
        favorite_repository.remove(
            user_id, track_id, "track"
        )

    def add_playlist(self, user_id: UUID, playlist_id: UUID) -> None:
        # Проверяем существование плейлиста
        if not external_client.playlist_exists(str(playlist_id)):
            raise ValueError("Playlist not found")

        favorite = Favorite(
            user_id=user_id,
            item_id=playlist_id,
            item_type="playlist"
        )

        favorite_repository.add(favorite)

    def remove_playlist(self, user_id: UUID, playlist_id: UUID) -> None:
        favorite_repository.remove(
            user_id, playlist_id, "playlist"
        )


favorite_service = FavoriteService()