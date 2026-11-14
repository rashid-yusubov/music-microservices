from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .auth import authenticated_user
from .config import Settings
from .database import Database
from .errors import ApiError
from .messaging import RabbitPublisher
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
from .service import CatalogService


def parse_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        raise ApiError(400, "BadRequest", "Некорректный UUID")


def create_app(settings: Settings | None = None, publisher: RabbitPublisher | None = None) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_path)
    repository = CatalogRepository(database)
    service = CatalogService(repository, publisher or RabbitPublisher(settings.rabbitmq_url))

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.initialize()
        yield

    app = FastAPI(title="Catalog Service", version="1.0.0", lifespan=lifespan)
    app.state.service = service

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

    @app.get("/api/v1/tracks", response_model=TrackPage)
    def list_tracks(
        query: str | None = None,
        artistId: UUID | None = None,
        albumId: UUID | None = None,
        offset: int = Query(default=0, ge=0),
        count: int = Query(default=20, ge=1, le=100),
    ):
        return repository.list_tracks(query, artistId, albumId, offset, count)

    @app.post("/api/v1/tracks", response_model=Track, status_code=201)
    def create_track(body: TrackCreateRequest, request: Request):
        authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.register_track(body)

    @app.get("/api/v1/tracks/{track_id}", response_model=Track)
    def get_track(track_id: str):
        return service.track(parse_uuid(track_id))

    @app.patch("/api/v1/tracks/{track_id}", response_model=Track)
    def patch_track(track_id: str, body: TrackPatchRequest, request: Request):
        authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.patch_track(parse_uuid(track_id), body)

    @app.post("/api/v1/tracks/{track_id}:approve", response_model=TrackApproveResponse)
    def approve_track(track_id: str, request: Request):
        authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.approve_track(parse_uuid(track_id))

    @app.post("/api/v1/tracks/{track_id}:reject", response_model=TrackRejectResponse)
    def reject_track(track_id: str, body: TrackRejectRequest, request: Request):
        authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.reject_track(parse_uuid(track_id), body)

    @app.get("/api/v1/albums", response_model=AlbumPage)
    def list_albums(
        query: str | None = None,
        offset: int = Query(default=0, ge=0),
        count: int = Query(default=20, ge=1, le=100),
    ):
        return service.list_albums(query, offset, count)

    @app.get("/api/v1/albums/{album_id}", response_model=Album)
    def get_album(album_id: str):
        return service.album(parse_uuid(album_id))

    @app.post("/api/v1/tracks/{track_id}:select", response_model=SelectionAccepted, status_code=202)
    def select_track(track_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.select(parse_uuid(track_id), user_id, album=False)

    @app.post("/api/v1/albums/{album_id}:select", response_model=SelectionAccepted, status_code=202)
    def select_album(album_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.select(parse_uuid(album_id), user_id, album=True)

    return app


app = create_app()
