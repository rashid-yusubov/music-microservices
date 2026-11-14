from uuid import UUID
from pydantic import BaseModel, Field


class PlaylistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    coverUrl: str | None = None


class AddTrackRequest(BaseModel):
    trackId: UUID


class TrackInfo(BaseModel):
    id: UUID
    title: str
    artist: str
    albumId: UUID | None = None
    durationSeconds: int | None = None
    status: str | None = None


class ReorderTracksRequest(BaseModel):
    trackIds: list[UUID]


class RenamePlaylistRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class UpdateCoverRequest(BaseModel):
    coverUrl: str = Field(min_length=1, max_length=1000)


class Playlist(BaseModel):
    id: UUID
    name: str
    ownerId: UUID
    description: str = ""
    trackIds: list[UUID] = Field(default_factory=list)
    coverUrl: str | None = None
    isPinned: bool = False
    createdAt: str


class ReorderResponse(BaseModel):
    playlistId: UUID
    trackIds: list[UUID]


class RenameResponse(BaseModel):
    id: UUID
    name: str
    ownerId: UUID


class CoverResponse(BaseModel):
    playlistId: UUID
    coverUrl: str


class PlaylistPage(BaseModel):
    items: list[Playlist]
    offset: int
    count: int
    total: int
