import os

import httpx


CATALOG_URL = os.getenv(
    "CATALOG_URL",
    "http://127.0.0.1:8003"
)

PLAYLISTS_URL = os.getenv(
    "PLAYLISTS_URL",
    "http://127.0.0.1:8004"
)


class ExternalServiceError(Exception):
    pass


class ExternalClient:

    def track_exists(self, track_id: str) -> bool:
        url = f"{CATALOG_URL}/api/v1/tracks/{track_id}"

        try:
            response = httpx.get(url, timeout=5.0)
        except httpx.RequestError:
            raise ExternalServiceError(
                "Music Catalog is unavailable"
            )

        if response.status_code == 404:
            return False

        if response.status_code != 200:
            raise ExternalServiceError(
                "Music Catalog returned an error"
            )

        return True

    def playlist_exists(self, playlist_id: str) -> bool:
        url = f"{PLAYLISTS_URL}/api/v1/playlists/{playlist_id}"

        try:
            response = httpx.get(url, timeout=5.0)
        except httpx.RequestError:
            raise ExternalServiceError(
                "Playlists Service is unavailable"
            )

        if response.status_code == 404:
            return False

        if response.status_code != 200:
            raise ExternalServiceError(
                "Playlists Service returned an error"
            )

        return True


external_client = ExternalClient()