import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import str_enum


class BoostTargetType(str, enum.Enum):
    MISSION = "mission"
    PROVIDER_PROFILE = "provider_profile"


class BoostStatus(str, enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    ACTIVE = "active"
    EXPIRED = "expired"


class Boost(Base):
    """Mise en avant payante (48h) d'une annonce ou d'un profil prestataire."""

    __tablename__ = "boosts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_type: Mapped[BoostTargetType] = mapped_column(
        str_enum(BoostTargetType, name="boost_target_type"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    amount_fcfa: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[BoostStatus] = mapped_column(
        str_enum(BoostStatus, name="boost_status"), default=BoostStatus.PENDING_PAYMENT, nullable=False
    )

    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
