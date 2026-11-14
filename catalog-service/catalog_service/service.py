from datetime import datetime, timezone
from uuid import UUID, uuid4

from .errors import ApiError
from .messaging import BrokerUnavailable, RabbitPublisher
from .models import (
    Album,
    AlbumPage,
    SelectionAccepted,
    Track,
    TrackApproveResponse,
    TrackCreateRequest,
    TrackPage,
    TrackPatchRequest,
    TrackRejectRequest,
    TrackRejectResponse,
)
from .repository import CatalogRepository


class CatalogService:
    def __init__(self, repository: CatalogRepository, publisher: RabbitPublisher):
        self.repository = repository
        self.publisher = publisher

    def track(self, track_id: UUID) -> Track:
        track = self.repository.get_track(track_id)
        if track is None:
            raise ApiError(404, "NotFound", "Трек не найден или не опубликован")
        return track

    def album(self, album_id: UUID) -> Album:
        album = self.repository.get_album(album_id)
        if album is None:
            raise ApiError(404, "NotFound", "Альбом не найден или не опубликован")
        return album

    def list_albums(self, query: str | None, offset: int, count: int) -> AlbumPage:
        return self.repository.list_albums(query, offset, count)

    def register_track(self, request: TrackCreateRequest) -> Track:
        track_id = uuid4()
        track = self.repository.create_track(
            track_id=track_id,
            title=request.title,
            artist=request.artist,
            album_id=request.albumId,
            media_id=request.mediaId,
            duration_seconds=request.durationSeconds,
        )
        if track is None:
            raise ApiError(404, "NotFound", "Альбом не найден")
        return track

    def patch_track(self, track_id: UUID, request: TrackPatchRequest) -> Track:
        track = self.repository.patch_track(track_id, request.title)
        if track is None:
            raise ApiError(404, "NotFound", "Трек не найден")
        return track

    def approve_track(self, track_id: UUID) -> TrackApproveResponse:
        track = self.repository.approve_track(track_id)
        if track is None:
            raise ApiError(404, "NotFound", "Трек не найден")
        return TrackApproveResponse(id=track.id, status="approved")

    def reject_track(self, track_id: UUID, request: TrackRejectRequest) -> TrackRejectResponse:
        res = self.repository.reject_track(track_id, request.reason)
        if res is None:
            raise ApiError(404, "NotFound", "Трек не найден")
        track, reason = res
        return TrackRejectResponse(id=track.id, status="rejected", reason=reason)

    def select(self, resource_id: UUID, user_id: UUID, *, album: bool) -> SelectionAccepted:
        if album:
            self.album(resource_id)
        else:
            self.track(resource_id)
        event_id = uuid4()
        event_type = "AlbumSelected" if album else "TrackSelected"
        event = {
            "eventId": str(event_id),
            "event": event_type,
            "userId": str(user_id),
            "albumId" if album else "trackId": str(resource_id),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        try:
            self.publisher.publish(event, "album.selected" if album else "track.selected")
        except BrokerUnavailable as exc:
            raise ApiError(503, "ServiceUnavailable", str(exc)) from exc
        return SelectionAccepted(eventId=event_id, event=event_type)
