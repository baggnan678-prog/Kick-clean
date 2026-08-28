import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.transaction import Transaction, TransactionStatus

router = APIRouter(prefix="/api/payments", tags=["payments"])
settings = get_settings()


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
