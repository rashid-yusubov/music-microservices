from uuid import UUID

import httpx
from pydantic import ValidationError

from .config import Settings
from .errors import ApiError
from .models import TrackInfo


class CatalogGateway:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.http_timeout, trust_env=False)
        self.owns_client = client is None

    def close(self) -> None:
        if self.owns_client:
            self.client.close()

    def get_track(self, track_id: UUID) -> TrackInfo:
        url = f"{self.settings.catalog_url.rstrip('/')}/api/v1/tracks/{track_id}"
        try:
            response = self.client.get(url, timeout=self.settings.http_timeout)
        except httpx.RequestError as exc:
            raise ApiError(503, "ServiceUnavailable", "Каталог недоступен") from exc
        if response.status_code == 404:
            raise ApiError(404, "NotFound", "Трек отсутствует в каталоге")
        if response.status_code >= 500:
            raise ApiError(503, "ServiceUnavailable", "Каталог временно недоступен")
        if response.status_code != 200:
            raise ApiError(502, "BadGateway", "Каталог вернул неожиданный статус")
        try:
            data = response.json()
        except ValueError as exc:
            raise ApiError(502, "BadGateway", "Каталог вернул невалидный JSON") from exc
        if not isinstance(data, dict):
            raise ApiError(502, "BadGateway", "Каталог вернул неверную структуру ответа")
        try:
            return TrackInfo.model_validate(data)
        except ValidationError as exc:
            raise ApiError(502, "BadGateway", "Нарушен контракт ответа каталога для трека") from exc
