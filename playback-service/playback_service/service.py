from uuid import UUID, uuid4

from .errors import ApiError
from .integrations import Gateway
from .models import PlaybackState, QueueItem, QueueResponse
from .repository import PlaybackRepository, Session


class PlaybackService:
    def __init__(self, repository: PlaybackRepository, gateway: Gateway):
        self.repository = repository
        self.gateway = gateway

    def state(self, user_id: UUID) -> PlaybackState:
        return self.repository.get(user_id).public()

    def start_track(self, user_id: UUID, track_id: UUID, event_id: UUID | None = None) -> None:
        if event_id is not None and self.repository.has_event(event_id):
            return
        track = self.gateway.get_track(track_id)
        self.gateway.require_subscription(user_id)
        item_id = uuid4()
        session = Session(
            status="playing",
            current_track_id=str(track.id),
            position_seconds=0,
            duration_seconds=track.durationSeconds,
            queue=[str(track.id)],
            queue_items=[{"id": str(item_id), "track_id": str(track.id)}],
            queue_index=0,
        )
        self.repository.save(user_id, session, event_id=event_id)

    def start_album(self, user_id: UUID, album_id: UUID, event_id: UUID | None = None) -> None:
        if event_id is not None and self.repository.has_event(event_id):
            return
        album = self.gateway.get_album(album_id)
        if not album.trackIds:
            raise ApiError(409, "Conflict", "В альбоме нет опубликованных треков")
        track = self.gateway.get_track(album.trackIds[0])
        self.gateway.require_subscription(user_id)
        queue_items = [{"id": str(uuid4()), "track_id": str(item)} for item in album.trackIds]
        session = Session(
            status="playing",
            current_track_id=str(track.id),
            album_id=str(album.id),
            position_seconds=0,
            duration_seconds=track.durationSeconds,
            queue=[str(item) for item in album.trackIds],
            queue_items=queue_items,
            queue_index=0,
        )
        self.repository.save(user_id, session, event_id=event_id)

    def pause(self, user_id: UUID) -> PlaybackState:
        session = self.repository.get(user_id)
        if session.status != "playing":
            raise ApiError(409, "Conflict", "Нет активного воспроизведения")
        session.status = "paused"
        self.repository.save(user_id, session)
        return session.public()

    def resume(self, user_id: UUID) -> PlaybackState:
        session = self.repository.get(user_id)
        if session.status != "paused" or not session.current_track_id:
            raise ApiError(409, "Conflict", "Нет приостановленного трека")
        self.gateway.get_track(UUID(session.current_track_id))
        self.gateway.require_subscription(user_id)
        session.status = "playing"
        self.repository.save(user_id, session)
        return session.public()

    def next_track(self, user_id: UUID) -> PlaybackState:
        session = self.repository.get(user_id)
        if not session.current_track_id or session.queue_index + 1 >= len(session.queue):
            raise ApiError(409, "Conflict", "Следующего трека нет")
        next_id = UUID(session.queue[session.queue_index + 1])
        track = self.gateway.get_track(next_id)
        self.gateway.require_subscription(user_id)
        session.current_track_id = str(track.id)
        session.queue_index += 1
        session.position_seconds = 0
        session.duration_seconds = track.durationSeconds
        session.status = "playing"
        self.repository.save(user_id, session)
        return session.public()

    def previous_track(self, user_id: UUID) -> PlaybackState:
        session = self.repository.get(user_id)
        if not session.current_track_id or session.queue_index <= 0:
            raise ApiError(409, "Conflict", "Предыдущего трека нет")
        prev_id = UUID(session.queue[session.queue_index - 1])
        track = self.gateway.get_track(prev_id)
        self.gateway.require_subscription(user_id)
        session.current_track_id = str(track.id)
        session.queue_index -= 1
        session.position_seconds = 0
        session.duration_seconds = track.durationSeconds
        session.status = "playing"
        self.repository.save(user_id, session)
        return session.public()

    def seek(self, user_id: UUID, position_seconds: int) -> PlaybackState:
        session = self.repository.get(user_id)
        if session.status not in ("playing", "paused") or not session.current_track_id:
            raise ApiError(409, "Conflict", "Нет активного воспроизведения")
        if position_seconds < 0 or (session.duration_seconds > 0 and position_seconds > session.duration_seconds):
            raise ApiError(400, "BadRequest", "Позиция вне диапазона длительности композиции")
        session.position_seconds = position_seconds
        self.repository.save(user_id, session)
        return session.public()

    def get_queue(self, user_id: UUID) -> QueueResponse:
        session = self.repository.get(user_id)
        items = [
            QueueItem(
                id=UUID(item["id"]),
                trackId=UUID(item["track_id"]),
                position=i,
            )
            for i, item in enumerate(session.queue_items)
        ]
        return QueueResponse(items=items)

    def add_to_queue(self, user_id: UUID, track_id: UUID) -> QueueItem:
        track = self.gateway.get_track(track_id)
        session = self.repository.get(user_id)
        item_id = uuid4()
        new_item = {"id": str(item_id), "track_id": str(track_id)}
        session.queue.append(str(track_id))
        session.queue_items.append(new_item)
        position = len(session.queue_items) - 1
        self.repository.save(user_id, session)
        return QueueItem(id=item_id, trackId=track_id, position=position)

    def remove_from_queue(self, user_id: UUID, queue_item_id: UUID) -> None:
        session = self.repository.get(user_id)
        idx = None
        for i, item in enumerate(session.queue_items):
            if item["id"] == str(queue_item_id):
                idx = i
                break
        if idx is None:
            raise ApiError(404, "NotFound", "Элемент очереди не найден")
        session.queue_items.pop(idx)
        if idx < len(session.queue):
            session.queue.pop(idx)
        if session.queue_index > idx:
            session.queue_index -= 1
        self.repository.save(user_id, session)

    def stop(self, user_id: UUID) -> None:
        self.repository.save(user_id, Session())
