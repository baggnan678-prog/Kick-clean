import hashlib
import hmac
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.config import get_settings
from app.core.paydunia import initiate_payment
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.mission import Mission
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User, UserRole
from app.schemas.transaction import PaymentInitiateResponse

router = APIRouter(prefix="/api/payments", tags=["payments"])
settings = get_settings()


@router.post("/missions/{mission_id}/initiate", response_model=PaymentInitiateResponse)
async def initiate_mission_payment(
    mission_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Le client obtient une URL de paiement Paydunia pour régler la mission acceptée.

    Les fonds ne passent en séquestre (HELD_IN_ESCROW) qu'à réception du
    webhook de confirmation (cf. paydunia_webhook ci-dessous), jamais avant.
    """
    mission = await db.get(Mission, mission_id)
    if mission is None or mission.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission introuvable")

    transaction = await db.scalar(select(Transaction).where(Transaction.mission_id == mission_id))
    if transaction is None or transaction.status != TransactionStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun paiement en attente pour cette mission",
        )

    result = await initiate_payment(
        amount_fcfa=transaction.amount_fcfa,
        description=f"ProxiServices — {mission.title}",
    )
    transaction.paydunia_reference = result["provider_reference"]

    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="payment_initiated",
            target_type="transaction",
            target_id=str(transaction.id),
        )
    )
    await db.commit()

    return {"payment_url": result["payment_url"]}


def _verify_signature(raw_body: bytes, signature: str) -> bool:
    """Vérifie la signature HMAC-SHA256 du webhook Paydunia pour empêcher toute falsification."""
    expected = hmac.new(settings.paydunia_webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook/paydunia", status_code=status.HTTP_204_NO_CONTENT)
async def paydunia_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_paydunia_signature: str = Header(...),
) -> None:
    raw_body = await request.body()
    if not _verify_signature(raw_body, x_paydunia_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Signature de webhook invalide")

    payload = await request.json()
    reference = payload.get("reference")
    new_status = payload.get("status")

    transaction = await db.scalar(select(Transaction).where(Transaction.paydunia_reference == reference))
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction introuvable")

    if new_status == "success":
        transaction.status = TransactionStatus.HELD_IN_ESCROW
    elif new_status == "failed":
        transaction.status = TransactionStatus.FAILED

    db.add(
        AuditLog(
            actor_id=None,
            action="paydunia_webhook",
            target_type="transaction",
            target_id=str(transaction.id),
            extra_data={"paydunia_status": new_status},
        )
    )
    await db.commit()
