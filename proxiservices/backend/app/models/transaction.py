import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    HELD_IN_ESCROW = "held_in_escrow"
    RELEASED = "released"
    REFUNDED = "refunded"
    FAILED = "failed"


class Transaction(Base):
    """Transaction en séquestre : les fonds sont bloqués jusqu'à validation de la prestation."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), nullable=False)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    amount_fcfa: Mapped[int] = mapped_column(nullable=False)
    commission_fcfa: Mapped[int] = mapped_column(nullable=False)

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False
    )
    paydunia_reference: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
