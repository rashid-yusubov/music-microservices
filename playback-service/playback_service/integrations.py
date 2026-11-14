import httpx
from pydantic import ValidationError
from uuid import UUID

from .config import Settings
from .errors import ApiError
from .models import AlbumInfo, SubscriptionInfo, TrackInfo
from .security import service_bearer


class Gateway:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.http_timeout, trust_env=False)
        self.owns_client = client is None

    def close(self) -> None:
        if self.owns_client:
            self.client.close()

    def _get(self, url: str, *, headers: dict | None = None, params: dict | None = None,
             not_found_message: str = "Объект не найден") -> dict:
        try:
            response = self.client.get(url, headers=headers, params=params,
                                       timeout=self.settings.http_timeout)
        except httpx.RequestError as exc:
            raise ApiError(503, "ServiceUnavailable", "Зависимый HTTP-сервис недоступен") from exc
        if response.status_code == 404:
            raise ApiError(404, "NotFound", not_found_message)
        if response.status_code >= 500:
            raise ApiError(503, "ServiceUnavailable", "Зависимый HTTP-сервис временно недоступен")
        if response.status_code != 200:
            raise ApiError(502, "BadGateway", "Зависимый HTTP-сервис вернул неожиданный статус")
        try:
            value = response.json()
        except ValueError as exc:
            raise ApiError(502, "BadGateway", "Зависимый HTTP-сервис вернул невалидный JSON") from exc
        if not isinstance(value, dict):
            raise ApiError(502, "BadGateway", "Зависимый HTTP-сервис вернул неверную структуру")
        return value

    def get_track(self, track_id: UUID) -> TrackInfo:
        data = self._get(f"{self.settings.catalog_url.rstrip('/')}/api/v1/tracks/{track_id}",
                         not_found_message="Трек отсутствует в каталоге")
        try:
            return TrackInfo.model_validate(data)
        except ValidationError as exc:
            raise ApiError(502, "BadGateway", "Нарушен контракт ответа каталога для трека") from exc

    def get_album(self, album_id: UUID) -> AlbumInfo:
        data = self._get(f"{self.settings.catalog_url.rstrip('/')}/api/v1/albums/{album_id}",
                         not_found_message="Альбом отсутствует в каталоге")
        try:
            return AlbumInfo.model_validate(data)
        except ValidationError as exc:
            raise ApiError(502, "BadGateway", "Нарушен контракт ответа каталога для альбома") from exc

    def require_subscription(self, user_id: UUID) -> None:
        try:
            data = self._get(
                f"{self.settings.subscription_url.rstrip('/')}/api/v1/subscriptions/status",
                params={"userId": str(user_id)},
                headers={"Authorization": service_bearer(self.settings.jwt_secret_key)},
                not_found_message="Подписка пользователя не найдена",
            )
        except ApiError as exc:
            if exc.status_code == 404:
                raise ApiError(403, "Forbidden", "Нет действующей подписки") from exc
            raise
        try:
            status = SubscriptionInfo.model_validate(data)
        except ValidationError as exc:
            raise ApiError(502, "BadGateway", "Нарушен контракт ответа сервиса подписок") from exc
        if status.userId != user_id:
            raise ApiError(502, "BadGateway", "Сервис подписок вернул другого пользователя")
        if not status.isActive:
            raise ApiError(403, "Forbidden", "Нет действующей подписки")
