import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import KycStatus, UserRole


class UserCreate(BaseModel):
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    full_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.CLIENT


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    phone: str | None
    full_name: str
    role: UserRole
    is_verified_provider: bool
    kyc_status: KycStatus


class KycRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
