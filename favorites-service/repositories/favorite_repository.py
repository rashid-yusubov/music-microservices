import os
import sqlite3
from pathlib import Path
from uuid import UUID

from models.favorite import Favorite


class FavoriteRepository:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.getenv("FAVORITES_DB_PATH")
        self.favorites: dict[tuple[UUID, UUID, str], Favorite] = {}
        if self.db_path:
            self._init_db()

    def _init_db(self) -> None:
        if self.db_path and self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path, timeout=10) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS favorites (
                    user_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    PRIMARY KEY (user_id, item_id, item_type)
                )
                """
            )
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def add(self, favorite: Favorite) -> None:
        if self.db_path:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO favorites (user_id, item_id, item_type) VALUES (?, ?, ?)",
                    (str(favorite.user_id), str(favorite.item_id), favorite.item_type),
                )
                conn.commit()
        else:
            key = (
                favorite.user_id,
                favorite.item_id,
                favorite.item_type,
            )
            self.favorites[key] = favorite

    def remove(
        self,
        user_id: UUID,
        item_id: UUID,
        item_type: str,
    ) -> None:
        if self.db_path:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM favorites WHERE user_id = ? AND item_id = ? AND item_type = ?",
                    (str(user_id), str(item_id), item_type),
                )
                conn.commit()
        else:
            key = (user_id, item_id, item_type)
            self.favorites.pop(key, None)

    def exists(
        self,
        user_id: UUID,
        item_id: UUID,
        item_type: str,
    ) -> bool:
        if self.db_path:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM favorites WHERE user_id = ? AND item_id = ? AND item_type = ?",
                    (str(user_id), str(item_id), item_type),
                )
                return cur.fetchone() is not None
        else:
            key = (user_id, item_id, item_type)
            return key in self.favorites

    def list_by_user(self, user_id: UUID) -> list[Favorite]:
        if self.db_path:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT user_id, item_id, item_type FROM favorites WHERE user_id = ?",
                    (str(user_id),),
                )
                return [
                    Favorite(
                        user_id=UUID(row["user_id"]),
                        item_id=UUID(row["item_id"]),
                        item_type=row["item_type"],
                    )
                    for row in cur.fetchall()
                ]
        else:
            return [
                fav for fav in self.favorites.values()
                if fav.user_id == user_id
            ]


favorite_repository = FavoriteRepository()
