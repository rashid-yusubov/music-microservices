import json
from dataclasses import dataclass, field
from uuid import UUID

from .database import Database
from .models import PlaybackState


@dataclass
class Session:
    status: str = "stopped"
    current_track_id: str | None = None
    album_id: str | None = None
    position_seconds: int = 0
    duration_seconds: int = 0
    queue: list[str] = field(default_factory=list)
    queue_index: int = 0
    queue_items: list[dict] = field(default_factory=list)

    def public(self) -> PlaybackState:
        return PlaybackState(
            status=self.status,
            currentTrackId=self.current_track_id,
            albumId=self.album_id,
            positionSeconds=self.position_seconds,
        )


class PlaybackRepository:
    def __init__(self, database: Database):
        self.database = database

    def get(self, user_id: UUID) -> Session:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM playback_states WHERE user_id=?", (str(user_id),)
            ).fetchone()
        if row is None:
            return Session()

        queue = json.loads(row["queue_json"])
        queue_items = []
        if "queue_items_json" in row.keys() and row["queue_items_json"]:
            try:
                queue_items = json.loads(row["queue_items_json"])
            except Exception:
                queue_items = []
        if not queue_items and queue:
            from uuid import uuid4
            queue_items = [{"id": str(uuid4()), "track_id": str(t)} for t in queue]

        return Session(
            status=row["status"],
            current_track_id=row["current_track_id"],
            album_id=row["album_id"],
            position_seconds=row["position_seconds"],
            duration_seconds=row["duration_seconds"],
            queue=queue,
            queue_index=row["queue_index"],
            queue_items=queue_items,
        )

    def save(self, user_id: UUID, session: Session, event_id: UUID | None = None) -> bool:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if event_id is not None:
                found = connection.execute(
                    "SELECT 1 FROM processed_events WHERE event_id=?", (str(event_id),)
                ).fetchone()
                if found:
                    return False
            connection.execute(
                """INSERT INTO playback_states (
                    user_id, status, current_track_id, album_id, position_seconds,
                    duration_seconds, queue_json, queue_index, queue_items_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     status=excluded.status,
                     current_track_id=excluded.current_track_id,
                     album_id=excluded.album_id,
                     position_seconds=excluded.position_seconds,
                     duration_seconds=excluded.duration_seconds,
                     queue_json=excluded.queue_json,
                     queue_index=excluded.queue_index,
                     queue_items_json=excluded.queue_items_json""",
                (
                    str(user_id),
                    session.status,
                    session.current_track_id,
                    session.album_id,
                    session.position_seconds,
                    session.duration_seconds,
                    json.dumps(session.queue),
                    session.queue_index,
                    json.dumps(session.queue_items),
                ),
            )
            if event_id is not None:
                connection.execute(
                    "INSERT INTO processed_events(event_id) VALUES (?)",
                    (str(event_id),),
                )
        return True

    def has_event(self, event_id: UUID) -> bool:
        with self.database.connect() as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM processed_events WHERE event_id=?", (str(event_id),)
                ).fetchone()
                is not None
            )
