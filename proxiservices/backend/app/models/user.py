import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import str_enum


class UserRole(str, enum.Enum):
    CLIENT = "client"
    PROVIDER = "provider"
    ADMIN = "admin"


class KycStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        str_enum(UserRole, name="user_role"), default=UserRole.CLIENT, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Badge "Vérifié" de l'abonnement Pro (cf. monétisation)
    is_verified_provider: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Vérification d'identité (KYC) des prestataires
    kyc_status: Mapped[KycStatus] = mapped_column(
        str_enum(KycStatus, name="kyc_status"), default=KycStatus.UNVERIFIED, nullable=False
    )
    kyc_document_path: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
