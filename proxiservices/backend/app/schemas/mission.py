import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.mission import MissionStatus, QuoteStatus


class MissionCreate(BaseModel):
    category_id: uuid.UUID
    title: str = Field(min_length=5, max_length=150)
    description: str = Field(min_length=10, max_length=3000)
    budget_fcfa: int = Field(gt=0, le=10_000_000)
    neighborhood: str = Field(min_length=2, max_length=150)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class MissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    provider_id: uuid.UUID | None
    category_id: uuid.UUID
    title: str
    description: str
    budget_fcfa: int
    neighborhood: str
    status: MissionStatus
    dispute_reason: str | None


class DisputeCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class DisputeResolve(BaseModel):
    resolution: Literal["release", "refund"]
    admin_note: str | None = Field(default=None, max_length=1000)


class MissionModerate(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class QuoteCreate(BaseModel):
    amount_fcfa: int = Field(gt=0, le=10_000_000)
    message: str | None = Field(default=None, max_length=1000)


class QuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    provider_id: uuid.UUID
    amount_fcfa: int
    message: str | None
    status: QuoteStatus
