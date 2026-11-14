import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SEED_PLAYLIST_ID = "660e8400-e29b-41d4-a716-446655440000"
SEED_OWNER_ID = "770e8400-e29b-41d4-a716-446655440000"
SEED_TRACK_ID = "550e8400-e29b-41d4-a716-446655440000"


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
            connection.execute("PRAGMA foreign_keys=ON")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    owner_id TEXT NOT NULL,
                    cover_url TEXT DEFAULT '',
                    is_pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id TEXT NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
                    track_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (playlist_id, track_id)
                );
            """)
            try:
                connection.execute("ALTER TABLE playlists ADD COLUMN cover_url TEXT DEFAULT ''")
            except Exception:
                pass
            try:
                connection.execute("ALTER TABLE playlists ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass

            connection.execute(
                """INSERT OR IGNORE INTO playlists (id, name, description, owner_id, cover_url, is_pinned, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (SEED_PLAYLIST_ID, "My Playlist", "Default test playlist", SEED_OWNER_ID, "", 0, "2026-11-12T07:00:00Z"),
            )
            connection.execute(
                """INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id, position)
                   VALUES (?, ?, ?)""",
                (SEED_PLAYLIST_ID, SEED_TRACK_ID, 1),
            )
