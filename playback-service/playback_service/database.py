import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import UUID


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
                CREATE TABLE IF NOT EXISTS playback_states (
                    user_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    current_track_id TEXT,
                    album_id TEXT,
                    position_seconds INTEGER NOT NULL DEFAULT 0,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    queue_json TEXT NOT NULL DEFAULT '[]',
                    queue_index INTEGER NOT NULL DEFAULT 0,
                    queue_items_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY
                );
            """)
            try:
                connection.execute("ALTER TABLE playback_states ADD COLUMN queue_items_json TEXT NOT NULL DEFAULT '[]'")
            except Exception:
                pass
