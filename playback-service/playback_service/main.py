from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from .config import Settings
from .consumer import RabbitConsumer
from .database import Database
from .errors import ApiError
from .integrations import Gateway
from .models import (
    AddQueueRequest,
    PlaybackState,
    QueueItem,
    QueueResponse,
    SeekRequest,
)
from .repository import PlaybackRepository
from .security import current_user
from .service import PlaybackService


def parse_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        raise ApiError(400, "BadRequest", "Некорректный UUID")


def create_app(settings: Settings | None = None, gateway: Gateway | None = None) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_path)
    repository = PlaybackRepository(database)
    gateway = gateway or Gateway(settings)
    service = PlaybackService(repository, gateway)
    consumer = RabbitConsumer(settings, service) if settings.consume_events else None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.initialize()
        if consumer is not None:
            consumer.start()
        try:
            yield
        finally:
            if consumer is not None:
                consumer.stop()
            gateway.close()

    app = FastAPI(title="Playback Service", version="1.0.0", lifespan=lifespan)
    app.state.service = service
    app.state.gateway = gateway

    def identity(request: Request):
        return current_user(request.headers.get("Authorization"), settings.jwt_secret_key)

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status_code,
                            content={"error": exc.error, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=400,
                            content={"error": "BadRequest", "message": "Некорректные параметры запроса"})

    @app.get("/api/v1/playback/state", response_model=PlaybackState)
    def state(request: Request):
        return service.state(identity(request))

    @app.post("/api/v1/playback:pause", response_model=PlaybackState)
    def pause(request: Request):
        return service.pause(identity(request))

    @app.post("/api/v1/playback:resume", response_model=PlaybackState)
    def resume(request: Request):
        return service.resume(identity(request))

    @app.post("/api/v1/playback:stop", status_code=204)
    def stop(request: Request):
        service.stop(identity(request))
        return Response(status_code=204)

    @app.post("/api/v1/playback:seek", response_model=PlaybackState)
    def seek(body: SeekRequest, request: Request):
        return service.seek(identity(request), body.positionSeconds)

    @app.post("/api/v1/playback:next", response_model=PlaybackState)
    def next_track(request: Request):
        return service.next_track(identity(request))

    @app.post("/api/v1/playback:previous", response_model=PlaybackState)
    def previous_track(request: Request):
        return service.previous_track(identity(request))

    @app.get("/api/v1/playback/queue", response_model=QueueResponse)
    def get_queue(request: Request):
        return service.get_queue(identity(request))

    @app.post("/api/v1/playback/queue", response_model=QueueItem, status_code=201)
    def add_to_queue(body: AddQueueRequest, request: Request):
        return service.add_to_queue(identity(request), body.trackId)

    @app.delete("/api/v1/playback/queue/{queue_item_id}", status_code=204)
    def remove_from_queue(queue_item_id: str, request: Request):
        service.remove_from_queue(identity(request), parse_uuid(queue_item_id))
        return Response(status_code=204)

    return app


app = create_app()
