from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SubscriptionStatus(BaseModel):
    userId: UUID
    isActive: bool
    status: str = "active"
    expiresAt: str | None = None


class CreateSubscriptionRequest(BaseModel):
    plan: str = Field(default="premium", max_length=50)
    durationDays: int = Field(default=30, ge=1, le=3650)
    planId: UUID | None = None
    paymentMethodId: UUID | None = None


class Subscription(BaseModel):
    id: UUID
    userId: UUID
    plan: str = "premium"
    planId: UUID | None = None
    status: Literal["active", "cancelled", "expired", "completed"] = "active"
    isActive: bool = True
    startDate: str | None = None
    startedAt: str | None = None
    expiresAt: str
    autoRenew: bool = True


class RenewSubscriptionResponse(BaseModel):
    id: UUID
    status: Literal["active"] = "active"
    expiresAt: str


class CompleteSubscriptionResponse(BaseModel):
    id: UUID
    status: Literal["completed"] = "completed"
    completedAt: str


class CancelSubscriptionResponse(BaseModel):
    id: UUID
    status: Literal["cancelled"] = "cancelled"
    cancelledAt: str
    expiresAt: str
