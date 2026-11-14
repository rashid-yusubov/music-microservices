from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlaybackState(BaseModel):
    status: Literal["playing", "paused", "stopped"] = "stopped"
    currentTrackId: UUID | None = None
    albumId: UUID | None = None
    positionSeconds: int = 0


class SeekRequest(BaseModel):
    positionSeconds: int = Field(ge=0)


class AddQueueRequest(BaseModel):
    trackId: UUID


class QueueItem(BaseModel):
    id: UUID
    trackId: UUID
    position: int


class QueueResponse(BaseModel):
    items: list[QueueItem]


class TrackInfo(BaseModel):
    id: UUID
    title: str
    artist: str
    albumId: UUID | None = None
    durationSeconds: int = Field(gt=0)
    status: Literal["approved"] = "approved"


class AlbumInfo(BaseModel):
    id: UUID
    title: str
    artist: str
    trackIds: list[UUID]


class SubscriptionInfo(BaseModel):
    userId: UUID
    isActive: bool
    expiresAt: str | None = None
