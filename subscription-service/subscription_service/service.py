from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from .errors import ApiError
from .models import (
    CancelSubscriptionResponse,
    CompleteSubscriptionResponse,
    CreateSubscriptionRequest,
    RenewSubscriptionResponse,
    Subscription,
    SubscriptionStatus,
)
from .repository import SubscriptionRepository


class SubscriptionService:
    def __init__(self, repository: SubscriptionRepository):
        self.repository = repository

    def get_status(self, user_id: UUID) -> SubscriptionStatus:
        active_sub = self.repository.get_active_by_user(user_id)
        if not active_sub:
            return SubscriptionStatus(userId=user_id, isActive=False, status="inactive", expiresAt=None)

        # Проверка срока действия
        try:
            expires_dt = datetime.fromisoformat(active_sub.expiresAt.replace("Z", "+00:00"))
            if expires_dt < datetime.now(timezone.utc):
                return SubscriptionStatus(userId=user_id, isActive=False, status="expired", expiresAt=None)
        except (ValueError, TypeError):
            pass

        return SubscriptionStatus(
            userId=user_id,
            isActive=True,
            status="active",
            expiresAt=active_sub.expiresAt,
        )

    def subscribe(self, user_id: UUID, request: CreateSubscriptionRequest) -> Subscription:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=request.durationDays)
        sub_id = uuid4()
        return self.repository.create_or_renew(
            subscription_id=sub_id,
            user_id=user_id,
            plan=request.plan,
            start_date=now.isoformat().replace("+00:00", "Z"),
            expires_at=expires.isoformat().replace("+00:00", "Z"),
            plan_id=request.planId,
            payment_method_id=request.paymentMethodId,
        )

    def get_my_subscription(self, user_id: UUID) -> Subscription:
        sub = self.repository.get_active_by_user(user_id) or self.repository.get_latest_by_user(user_id)
        if not sub:
            raise ApiError(404, "NotFound", "Подписка пользователя не найдена")
        return sub

    def cancel_subscription(self, user_id: UUID) -> Subscription:
        cancelled = self.repository.cancel_active_by_user(user_id)
        if not cancelled:
            raise ApiError(404, "NotFound", "Нет активной подписки для отмены")
        return cancelled

    def renew_subscription(self, subscription_id: UUID, user_id: UUID) -> RenewSubscriptionResponse:
        sub = self.repository.get_by_id(subscription_id)
        if not sub:
            raise ApiError(404, "NotFound", "Подписка не найдена")
        if sub.userId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для управления этой подпиской")

        now = datetime.now(timezone.utc)
        try:
            current_expires = datetime.fromisoformat(sub.expiresAt.replace("Z", "+00:00"))
            base_date = max(now, current_expires)
        except Exception:
            base_date = now
        new_expires = (base_date + timedelta(days=30)).isoformat().replace("+00:00", "Z")

        updated = self.repository.renew(subscription_id, new_expires)
        return RenewSubscriptionResponse(id=subscription_id, status="active", expiresAt=updated.expiresAt)

    def complete_subscription(self, subscription_id: UUID) -> CompleteSubscriptionResponse:
        sub = self.repository.get_by_id(subscription_id)
        if not sub:
            raise ApiError(404, "NotFound", "Подписка не найдена")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.repository.complete(subscription_id, now)
        return CompleteSubscriptionResponse(id=subscription_id, status="completed", completedAt=now)

    def cancel_subscription_by_id(self, subscription_id: UUID, user_id: UUID) -> CancelSubscriptionResponse:
        sub = self.repository.get_by_id(subscription_id)
        if not sub:
            raise ApiError(404, "NotFound", "Подписка не найдена")
        if sub.userId != user_id:
            raise ApiError(403, "Forbidden", "Нет прав для управления этой подпиской")

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.repository.cancel_by_id(subscription_id, now)
        return CancelSubscriptionResponse(
            id=subscription_id,
            status="cancelled",
            cancelledAt=now,
            expiresAt=sub.expiresAt,
        )
