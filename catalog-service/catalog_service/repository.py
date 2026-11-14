from uuid import UUID

from .database import Database
from .models import Album, AlbumPage, AlbumSummary, Track, TrackPage


class CatalogRepository:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _track(row) -> Track:
        return Track(
            id=row["id"],
            title=row["title"],
            artist=row["artist"],
            albumId=row["album_id"],
            durationSeconds=row["duration_seconds"],
            status=row["status"],
        )

    def get_track(self, track_id: UUID) -> Track | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracks WHERE id=? AND status='approved'", (str(track_id),)
            ).fetchone()
        return self._track(row) if row else None

    def get_track_any_status(self, track_id: UUID) -> Track | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracks WHERE id=?", (str(track_id),)
            ).fetchone()
        return self._track(row) if row else None

    def list_tracks(
        self,
        query: str | None,
        artist_id: UUID | None,
        album_id: UUID | None,
        offset: int,
        count: int,
    ) -> TrackPage:
        conditions = ["status='approved'"]
        params: list[object] = []
        if query:
            conditions.append("(title LIKE ? OR artist LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        if artist_id:
            conditions.append("artist_id=?")
            params.append(str(artist_id))
        if album_id:
            conditions.append("album_id=?")
            params.append(str(album_id))
        where = " AND ".join(conditions)
        with self.database.connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM tracks WHERE {where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM tracks WHERE {where} ORDER BY title, id LIMIT ? OFFSET ?",
                [*params, count, offset],
            ).fetchall()
        return TrackPage(
            items=[self._track(row) for row in rows],
            offset=offset,
            count=count,
            total=total,
        )

    def get_album(self, album_id: UUID) -> Album | None:
        with self.database.connect() as connection:
            album = connection.execute(
                "SELECT * FROM albums WHERE id=?", (str(album_id),)
            ).fetchone()
            if not album:
                return None
            tracks = connection.execute(
                """SELECT id FROM tracks WHERE album_id=? AND status='approved'
                   ORDER BY track_number, id""",
                (str(album_id),),
            ).fetchall()
        if not tracks:
            return None
        return Album(
            id=album["id"],
            title=album["title"],
            artist=album["artist"],
            trackIds=[row["id"] for row in tracks],
        )

    def list_albums(self, query: str | None, offset: int, count: int) -> AlbumPage:
        conditions = []
        params: list[object] = []
        if query:
            conditions.append("(title LIKE ? OR artist LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self.database.connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM albums {where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM albums {where} ORDER BY title, id LIMIT ? OFFSET ?",
                [*params, count, offset],
            ).fetchall()
        return AlbumPage(
            items=[
                AlbumSummary(id=row["id"], title=row["title"], artist=row["artist"])
                for row in rows
            ],
            offset=offset,
            count=count,
            total=total,
        )

    def create_track(
        self,
        track_id: UUID,
        title: str,
        artist: str,
        album_id: UUID,
        media_id: UUID,
        duration_seconds: int,
    ) -> Track | None:
        with self.database.connect() as connection:
            album = connection.execute(
                "SELECT * FROM albums WHERE id=?", (str(album_id),)
            ).fetchone()
            if not album:
                return None
            last_num = connection.execute(
                "SELECT COALESCE(MAX(track_number), 0) FROM tracks WHERE album_id=?",
                (str(album_id),),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO tracks
                   (id, title, artist, artist_id, album_id, duration_seconds, status, track_number, media_id)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
                (
                    str(track_id),
                    title,
                    artist,
                    album["artist_id"],
                    str(album_id),
                    duration_seconds,
                    last_num + 1,
                    str(media_id),
                ),
            )
        return Track(
            id=track_id,
            title=title,
            artist=artist,
            albumId=album_id,
            durationSeconds=duration_seconds,
            status="pending",
        )

    def patch_track(self, track_id: UUID, title: str | None) -> Track | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracks WHERE id=?", (str(track_id),)
            ).fetchone()
            if not row:
                return None
            new_title = title if title is not None else row["title"]
            connection.execute(
                "UPDATE tracks SET title=?, status='pending' WHERE id=?",
                (new_title, str(track_id)),
            )
        return Track(
            id=row["id"],
            title=new_title,
            artist=row["artist"],
            albumId=row["album_id"],
            durationSeconds=row["duration_seconds"],
            status="pending",
        )

    def approve_track(self, track_id: UUID) -> Track | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracks WHERE id=?", (str(track_id),)
            ).fetchone()
            if not row:
                return None
            connection.execute(
                "UPDATE tracks SET status='approved' WHERE id=?", (str(track_id),)
            )
        return Track(
            id=row["id"],
            title=row["title"],
            artist=row["artist"],
            albumId=row["album_id"],
            durationSeconds=row["duration_seconds"],
            status="approved",
        )

    def reject_track(self, track_id: UUID, reason: str) -> tuple[Track, str] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracks WHERE id=?", (str(track_id),)
            ).fetchone()
            if not row:
                return None
            connection.execute(
                "UPDATE tracks SET status='rejected', reject_reason=? WHERE id=?",
                (reason, str(track_id)),
            )
        return (
            Track(
                id=row["id"],
                title=row["title"],
                artist=row["artist"],
                albumId=row["album_id"],
                durationSeconds=row["duration_seconds"],
                status="rejected",
            ),
            reason,
        )
