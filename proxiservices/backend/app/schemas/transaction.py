import uuid

from pydantic import BaseModel, ConfigDict

from app.models.transaction import TransactionStatus


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    amount_fcfa: int
    commission_fcfa: int
    status: TransactionStatus
    paydunia_reference: str | None
