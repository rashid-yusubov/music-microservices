import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_path: str = field(default_factory=lambda: os.getenv("PLAYLISTS_DB_PATH", "/data/playlists.sqlite3"))
    catalog_url: str = field(default_factory=lambda: os.getenv("CATALOG_URL", "http://catalog-service:8003"))
    jwt_secret_key: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))
    http_timeout: float = field(default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_SECONDS", "3")))
