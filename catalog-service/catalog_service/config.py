import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_path: str = field(default_factory=lambda: os.getenv("CATALOG_DB_PATH", "/data/catalog.sqlite3"))
    rabbitmq_url: str = field(default_factory=lambda: os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/%2F"))
    jwt_secret_key: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))
