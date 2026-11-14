from uuid import UUID

from .database import Database
from .models import Playlist


class PlaylistRepository:
    def __init__(self, database: Database):
        self.database = database

    def _get_track_ids(self, connection, playlist_id: str) -> list[UUID]:
        rows = connection.execute(
            "SELECT track_id FROM playlist_tracks WHERE playlist_id = ? ORDER BY position ASC",
            (playlist_id,),
        ).fetchall()
        return [UUID(row["track_id"]) for row in rows]

    def get_playlist(self, playlist_id: UUID) -> Playlist | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT id, name, description, owner_id, cover_url, is_pinned, created_at
                   FROM playlists WHERE id = ?""",
                (str(playlist_id),),
            ).fetchone()
            if not row:
                return None
            track_ids = self._get_track_ids(connection, str(playlist_id))
            return Playlist(
                id=UUID(row["id"]),
                name=row["name"],
                description=row["description"],
                ownerId=UUID(row["owner_id"]),
                trackIds=track_ids,
                coverUrl=row["cover_url"] or None,
                isPinned=bool(row["is_pinned"]),
                createdAt=row["created_at"],
            )

    def list_playlists(
        self,
        query: str | None,
        owner_id: UUID | None,
        offset: int,
        count: int,
    ) -> tuple[list[Playlist], int]:
        filters: list[str] = []
        params: list[object] = []
        if query:
            filters.append("name LIKE ?")
            params.append(f"%{query}%")
        if owner_id:
            filters.append("owner_id = ?")
            params.append(str(owner_id))

        where_clause = f" WHERE {' AND '.join(filters)}" if filters else ""

        with self.database.connect() as connection:
            total_row = connection.execute(
                f"SELECT COUNT(*) AS total FROM playlists{where_clause}",
                params,
            ).fetchone()
            total = int(total_row["total"]) if total_row else 0

            rows = connection.execute(
                f"""SELECT id, name, description, owner_id, cover_url, is_pinned, created_at
                    FROM playlists{where_clause}
                    ORDER BY is_pinned DESC, created_at DESC
                    LIMIT ? OFFSET ?""",
                params + [count, offset],
            ).fetchall()

            items = [
                Playlist(
                    id=UUID(row["id"]),
                    name=row["name"],
                    description=row["description"],
                    ownerId=UUID(row["owner_id"]),
                    trackIds=self._get_track_ids(connection, row["id"]),
                    coverUrl=row["cover_url"] or None,
                    isPinned=bool(row["is_pinned"]),
                    createdAt=row["created_at"],
                )
                for row in rows
            ]
            return items, total

    def create_playlist(
        self,
        playlist_id: UUID,
        name: str,
        description: str,
        owner_id: UUID,
        cover_url: str | None,
        created_at: str,
    ) -> Playlist:
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO playlists (id, name, description, owner_id, cover_url, is_pinned, created_at)
                   VALUES (?, ?, ?, ?, ?, 0, ?)""",
                (str(playlist_id), name, description, str(owner_id), cover_url or "", created_at),
            )
            return Playlist(
                id=playlist_id,
                name=name,
                description=description,
                ownerId=owner_id,
                trackIds=[],
                coverUrl=cover_url,
                isPinned=False,
                createdAt=created_at,
            )

    def add_track(self, playlist_id: UUID, track_id: UUID) -> None:
        with self.database.connect() as connection:
            max_pos_row = connection.execute(
                "SELECT COALESCE(MAX(position), 0) AS max_pos FROM playlist_tracks WHERE playlist_id = ?",
                (str(playlist_id),),
            ).fetchone()
            next_pos = int(max_pos_row["max_pos"]) + 1 if max_pos_row else 1
            connection.execute(
                """INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position)
                   VALUES (?, ?, ?)""",
                (str(playlist_id), str(track_id), next_pos),
            )

    def remove_track(self, playlist_id: UUID, track_id: UUID) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                (str(playlist_id), str(track_id)),
            )
            return cursor.rowcount > 0

    def reorder_tracks(self, playlist_id: UUID, track_ids: list[UUID]) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (str(playlist_id),))
            connection.executemany(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                [(str(playlist_id), str(t), i + 1) for i, t in enumerate(track_ids)],
            )

    def rename_playlist(self, playlist_id: UUID, name: str) -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE playlists SET name = ? WHERE id = ?", (name, str(playlist_id)))

    def update_cover(self, playlist_id: UUID, cover_url: str) -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE playlists SET cover_url = ? WHERE id = ?", (cover_url, str(playlist_id)))

    def set_pinned(self, playlist_id: UUID, is_pinned: bool) -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE playlists SET is_pinned = ? WHERE id = ?", (1 if is_pinned else 0, str(playlist_id)))

    def delete_playlist(self, playlist_id: UUID) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM playlists WHERE id = ?",
                (str(playlist_id),),
            )
            return cursor.rowcount > 0
