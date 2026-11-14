import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_path: str = field(default_factory=lambda: os.getenv("PLAYBACK_DB_PATH", "/data/playback.sqlite3"))
    catalog_url: str = field(default_factory=lambda: os.getenv("CATALOG_URL", "http://catalog-service:8003"))
    subscription_url: str = field(default_factory=lambda: os.getenv("SUBSCRIPTION_URL", "http://subscription-service:8005"))
    rabbitmq_url: str = field(default_factory=lambda: os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/%2F"))
    jwt_secret_key: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))
    http_timeout: float = field(default_factory=lambda: float(os.getenv("HTTP_TIMEOUT_SECONDS", "3")))
    consume_events: bool = field(default_factory=lambda: os.getenv("CONSUME_EVENTS", "true").lower() == "true")
