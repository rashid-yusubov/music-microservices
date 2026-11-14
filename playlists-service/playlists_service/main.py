from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .auth import authenticated_user
from .config import Settings
from .database import Database
from .errors import ApiError
from .integrations import CatalogGateway
from .models import (
    AddTrackRequest,
    CoverResponse,
    Playlist,
    PlaylistCreate,
    PlaylistPage,
    RenamePlaylistRequest,
    RenameResponse,
    ReorderResponse,
    ReorderTracksRequest,
    UpdateCoverRequest,
)
from .repository import PlaylistRepository
from .service import PlaylistService


def parse_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        raise ApiError(400, "BadRequest", "Некорректный UUID")


def create_app(settings: Settings | None = None, catalog_gateway: CatalogGateway | None = None) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_path)
    repository = PlaylistRepository(database)
    gateway = catalog_gateway or CatalogGateway(settings)
    service = PlaylistService(repository, gateway)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.initialize()
        yield
        gateway.close()

    app = FastAPI(title="Playlists Service", version="1.0.0", lifespan=lifespan)
    app.state.service = service
    app.state.gateway = gateway
    app.state.settings = settings

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.error, "message": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": "BadRequest", "message": "Некорректные параметры запроса"},
        )

    @app.get("/api/v1/playlists", response_model=PlaylistPage)
    def list_playlists(
        query: str | None = None,
        ownerId: UUID | None = None,
        offset: int = Query(default=0, ge=0),
        count: int = Query(default=20, ge=1, le=100),
    ):
        return service.list_playlists(query=query, owner_id=ownerId, offset=offset, count=count)

    @app.post("/api/v1/playlists", response_model=Playlist, status_code=201)
    def create_playlist(data: PlaylistCreate, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.create_playlist(data, user_id)

    @app.get("/api/v1/playlists/{playlist_id}", response_model=Playlist)
    def get_playlist(playlist_id: str):
        return service.get_playlist(parse_uuid(playlist_id))

    @app.post("/api/v1/playlists/{playlist_id}/tracks", response_model=Playlist)
    def add_track_to_playlist(playlist_id: str, body: AddTrackRequest, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.add_track(parse_uuid(playlist_id), body.trackId, user_id)

    @app.delete("/api/v1/playlists/{playlist_id}/tracks/{track_id}", status_code=204)
    def remove_track_from_playlist(playlist_id: str, track_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        service.remove_track(parse_uuid(playlist_id), parse_uuid(track_id), user_id)
        return Response(status_code=204)

    @app.patch("/api/v1/playlists/{playlist_id}/tracks/order", response_model=ReorderResponse)
    def reorder_tracks(playlist_id: str, body: ReorderTracksRequest, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.reorder_tracks(parse_uuid(playlist_id), body.trackIds, user_id)

    @app.patch("/api/v1/playlists/{playlist_id}", response_model=RenameResponse)
    def rename_playlist(playlist_id: str, body: RenamePlaylistRequest, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.rename_playlist(parse_uuid(playlist_id), body.name, user_id)

    @app.put("/api/v1/playlists/{playlist_id}/cover", response_model=CoverResponse)
    def update_cover(playlist_id: str, body: UpdateCoverRequest, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.update_cover(parse_uuid(playlist_id), body.coverUrl, user_id)

    @app.put("/api/v1/playlists/{playlist_id}/pin", status_code=204)
    def pin_playlist(playlist_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        service.pin_playlist(parse_uuid(playlist_id), user_id)
        return Response(status_code=204)

    @app.delete("/api/v1/playlists/{playlist_id}/pin", status_code=204)
    def unpin_playlist(playlist_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        service.unpin_playlist(parse_uuid(playlist_id), user_id)
        return Response(status_code=204)

    @app.delete("/api/v1/playlists/{playlist_id}", status_code=204)
    def delete_playlist(playlist_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        service.delete_playlist(parse_uuid(playlist_id), user_id)
        return Response(status_code=204)

    return app


app = create_app()
