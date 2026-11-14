from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Track(BaseModel):
    id: UUID
    title: str
    artist: str
    albumId: UUID
    durationSeconds: int = Field(ge=1)
    status: Literal["approved", "pending", "rejected"] = "approved"


class TrackCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    artist: str = Field(min_length=1, max_length=200)
    albumId: UUID
    mediaId: UUID
    durationSeconds: int = Field(ge=1)


class TrackPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)


class TrackApproveResponse(BaseModel):
    id: UUID
    status: Literal["approved"] = "approved"


class TrackRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class TrackRejectResponse(BaseModel):
    id: UUID
    status: Literal["rejected"] = "rejected"
    reason: str


class Album(BaseModel):
    id: UUID
    title: str
    artist: str
    trackIds: list[UUID]


class AlbumSummary(BaseModel):
    id: UUID
    title: str
    artist: str


class AlbumPage(BaseModel):
    items: list[AlbumSummary]
    offset: int
    count: int
    total: int


class TrackPage(BaseModel):
    items: list[Track]
    offset: int
    count: int
    total: int


class SelectionAccepted(BaseModel):
    eventId: UUID
    event: Literal["TrackSelected", "AlbumSelected"]
    status: Literal["accepted"] = "accepted"
