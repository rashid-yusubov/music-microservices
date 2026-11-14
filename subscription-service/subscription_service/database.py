import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SEED_USER_ID = "770e8400-e29b-41d4-a716-446655440000"
SEED_SUBSCRIPTION_ID = "880e8400-e29b-41d4-a716-446655440000"


class Database:
    def __init__(self, path: str):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_active INTEGER NOT NULL CHECK(is_active IN (0, 1)),
                    start_date TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    auto_renew INTEGER NOT NULL CHECK(auto_renew IN (0, 1)) DEFAULT 1,
                    plan_id TEXT,
                    payment_method_id TEXT,
                    completed_at TEXT,
                    cancelled_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
            """)
            for col in ("plan_id", "payment_method_id", "completed_at", "cancelled_at"):
                try:
                    connection.execute(f"ALTER TABLE subscriptions ADD COLUMN {col} TEXT")
                except Exception:
                    pass

            connection.execute(
                """INSERT OR IGNORE INTO subscriptions
                   (id, user_id, plan, status, is_active, start_date, expires_at, auto_renew)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    SEED_SUBSCRIPTION_ID,
                    SEED_USER_ID,
                    "premium",
                    "active",
                    1,
                    "2026-11-12T07:00:00Z",
                    "2027-12-31T23:59:59Z",
                    1,
                ),
            )
