from uuid import UUID

from .database import Database
from .models import Subscription


class SubscriptionRepository:
    def __init__(self, database: Database):
        self.database = database

    def _row_to_model(self, row) -> Subscription:
        plan_id = None
        if "plan_id" in row.keys() and row["plan_id"]:
            try:
                plan_id = UUID(row["plan_id"])
            except Exception:
                plan_id = None

        return Subscription(
            id=UUID(row["id"]),
            userId=UUID(row["user_id"]),
            plan=row["plan"],
            planId=plan_id,
            status=row["status"],
            isActive=bool(row["is_active"]),
            startDate=row["start_date"],
            startedAt=row["start_date"],
            expiresAt=row["expires_at"],
            autoRenew=bool(row["auto_renew"]),
        )

    def get_by_id(self, subscription_id: UUID) -> Subscription | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM subscriptions WHERE id = ?""",
                (str(subscription_id),),
            ).fetchone()
            return self._row_to_model(row) if row else None

    def get_active_by_user(self, user_id: UUID) -> Subscription | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM subscriptions
                   WHERE user_id = ? AND is_active = 1 AND status = 'active'
                   ORDER BY expires_at DESC
                   LIMIT 1""",
                (str(user_id),),
            ).fetchone()
            return self._row_to_model(row) if row else None

    def get_latest_by_user(self, user_id: UUID) -> Subscription | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM subscriptions
                   WHERE user_id = ?
                   ORDER BY start_date DESC
                   LIMIT 1""",
                (str(user_id),),
            ).fetchone()
            return self._row_to_model(row) if row else None

    def create_or_renew(
        self,
        subscription_id: UUID,
        user_id: UUID,
        plan: str,
        start_date: str,
        expires_at: str,
        plan_id: UUID | None = None,
        payment_method_id: UUID | None = None,
    ) -> Subscription:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
                (str(user_id),),
            )
            connection.execute(
                """INSERT INTO subscriptions
                   (id, user_id, plan, status, is_active, start_date, expires_at, auto_renew, plan_id, payment_method_id)
                   VALUES (?, ?, ?, 'active', 1, ?, ?, 1, ?, ?)""",
                (
                    str(subscription_id),
                    str(user_id),
                    plan,
                    start_date,
                    expires_at,
                    str(plan_id) if plan_id else None,
                    str(payment_method_id) if payment_method_id else None,
                ),
            )
            return Subscription(
                id=subscription_id,
                userId=user_id,
                plan=plan,
                planId=plan_id,
                status="active",
                isActive=True,
                startDate=start_date,
                startedAt=start_date,
                expiresAt=expires_at,
                autoRenew=True,
            )

    def renew(self, subscription_id: UUID, new_expires_at: str) -> Subscription | None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE subscriptions SET status = 'active', is_active = 1, expires_at = ? WHERE id = ?",
                (new_expires_at, str(subscription_id)),
            )
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ?", (str(subscription_id),)
            ).fetchone()
            return self._row_to_model(row) if row else None

    def complete(self, subscription_id: UUID, completed_at: str) -> Subscription | None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE subscriptions SET status = 'completed', is_active = 0, auto_renew = 0, completed_at = ? WHERE id = ?",
                (completed_at, str(subscription_id)),
            )
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ?", (str(subscription_id),)
            ).fetchone()
            return self._row_to_model(row) if row else None

    def cancel_by_id(self, subscription_id: UUID, cancelled_at: str) -> Subscription | None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE subscriptions SET status = 'cancelled', is_active = 0, auto_renew = 0, cancelled_at = ? WHERE id = ?",
                (cancelled_at, str(subscription_id)),
            )
            row = connection.execute(
                "SELECT * FROM subscriptions WHERE id = ?", (str(subscription_id),)
            ).fetchone()
            return self._row_to_model(row) if row else None

    def cancel_active_by_user(self, user_id: UUID) -> Subscription | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """SELECT id FROM subscriptions
                   WHERE user_id = ? AND is_active = 1
                   ORDER BY expires_at DESC
                   LIMIT 1""",
                (str(user_id),),
            ).fetchone()
            if not row:
                return None
            sub_id = row["id"]
            connection.execute(
                "UPDATE subscriptions SET status = 'cancelled', is_active = 0, auto_renew = 0 WHERE id = ?",
                (sub_id,),
            )
            updated_row = connection.execute(
                """SELECT * FROM subscriptions WHERE id = ?""",
                (sub_id,),
            ).fetchone()
            return self._row_to_model(updated_row) if updated_row else None
