import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_path: str = field(default_factory=lambda: os.getenv("SUBSCRIPTION_DB_PATH", "/data/subscription.sqlite3"))
    jwt_secret_key: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY", ""))
