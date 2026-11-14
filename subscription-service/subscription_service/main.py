from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .auth import authenticated_user, verify_service_or_user
from .config import Settings
from .database import Database
from .errors import ApiError
from .models import (
    CancelSubscriptionResponse,
    CompleteSubscriptionResponse,
    CreateSubscriptionRequest,
    RenewSubscriptionResponse,
    Subscription,
    SubscriptionStatus,
)
from .repository import SubscriptionRepository
from .service import SubscriptionService


def parse_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError):
        raise ApiError(400, "BadRequest", "Некорректный UUID")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    database = Database(settings.database_path)
    repository = SubscriptionRepository(database)
    service = SubscriptionService(repository)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database.initialize()
        yield

    app = FastAPI(title="Subscription Service", version="1.0.0", lifespan=lifespan)
    app.state.service = service
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

    @app.get("/api/v1/subscriptions/status", response_model=SubscriptionStatus)
    def get_subscription_status(userId: str = Query(...), request: Request = None):
        auth_header = request.headers.get("Authorization") if request else None
        if auth_header:
            verify_service_or_user(auth_header, settings.jwt_secret_key)
        return service.get_status(parse_uuid(userId))

    @app.post("/api/v1/subscriptions", response_model=Subscription, status_code=201)
    def create_subscription(body: CreateSubscriptionRequest, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.subscribe(user_id, body)

    @app.post("/api/v1/subscriptions/{subscription_id}/renew", response_model=RenewSubscriptionResponse)
    def renew_subscription(subscription_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.renew_subscription(parse_uuid(subscription_id), user_id)

    @app.post("/api/v1/subscriptions/{subscription_id}/complete", response_model=CompleteSubscriptionResponse)
    def complete_subscription(subscription_id: str, request: Request):
        verify_service_or_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.complete_subscription(parse_uuid(subscription_id))

    @app.post("/api/v1/subscriptions/{subscription_id}/cancel", response_model=CancelSubscriptionResponse)
    def cancel_subscription_by_id(subscription_id: str, request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.cancel_subscription_by_id(parse_uuid(subscription_id), user_id)

    @app.get("/api/v1/subscriptions/my", response_model=Subscription)
    def get_my_subscription(request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.get_my_subscription(user_id)

    @app.post("/api/v1/subscriptions/cancel", response_model=Subscription)
    def cancel_subscription(request: Request):
        user_id = authenticated_user(request.headers.get("Authorization"), settings.jwt_secret_key)
        return service.cancel_subscription(user_id)

    return app


app = create_app()
