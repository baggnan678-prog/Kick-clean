import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.boost import BoostStatus, BoostTargetType


class BoostCreate(BaseModel):
    target_type: BoostTargetType
    target_id: uuid.UUID


class BoostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    target_type: BoostTargetType
    target_id: uuid.UUID
    amount_fcfa: int
    status: BoostStatus
    starts_at: datetime | None
    ends_at: datetime | None
