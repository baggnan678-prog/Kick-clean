import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.subscription import SubscriptionPlan, SubscriptionStatus


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider_id: uuid.UUID
    plan: SubscriptionPlan
    status: SubscriptionStatus
    started_at: datetime
    expires_at: datetime | None


class SubscriptionActivate(BaseModel):
    duration_days: int = Field(default=30, gt=0, le=365)
