import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SEED_ALBUM_ID = "770e8400-e29b-41d4-a716-446655440002"
SEED_TRACK_ID = "550e8400-e29b-41d4-a716-446655440000"
SEED_SECOND_TRACK_ID = "660e8400-e29b-41d4-a716-446655440003"
SEED_ARTIST_ID = "990e8400-e29b-41d4-a716-446655440009"


class Database:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS albums (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    artist_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tracks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    artist_id TEXT NOT NULL,
                    album_id TEXT NOT NULL REFERENCES albums(id),
                    duration_seconds INTEGER NOT NULL CHECK(duration_seconds > 0),
                    status TEXT NOT NULL CHECK(status IN ('approved','pending','rejected')),
                    track_number INTEGER NOT NULL,
                    media_id TEXT,
                    reject_reason TEXT
                );
            """)
            try:
                connection.execute("ALTER TABLE tracks ADD COLUMN media_id TEXT")
            except Exception:
                pass
            try:
                connection.execute("ALTER TABLE tracks ADD COLUMN reject_reason TEXT")
            except Exception:
                pass

            connection.execute(
                "INSERT OR IGNORE INTO albums (id, title, artist, artist_id) VALUES (?, ?, ?, ?)",
                (SEED_ALBUM_ID, "Example Album", "Example Artist", SEED_ARTIST_ID),
            )
            connection.executemany(
                """INSERT OR IGNORE INTO tracks
                   (id,title,artist,artist_id,album_id,duration_seconds,status,track_number)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [
                    (SEED_TRACK_ID, "Example Track", "Example Artist", SEED_ARTIST_ID,
                     SEED_ALBUM_ID, 215, "approved", 1),
                    (SEED_SECOND_TRACK_ID, "Second Track", "Example Artist", SEED_ARTIST_ID,
                     SEED_ALBUM_ID, 198, "approved", 2),
                ],
            )
