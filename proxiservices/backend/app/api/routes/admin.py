import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.storage import create_signed_url
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.mission import Mission, MissionStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import KycStatus, User, UserRole
from app.schemas.mission import MissionRead
from app.schemas.user import KycRejectRequest, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role(UserRole.ADMIN))])


@router.get("/disputes", response_model=list[MissionRead])
async def list_disputes(db: AsyncSession = Depends(get_db)) -> list[Mission]:
    result = await db.scalars(select(Mission).where(Mission.status == MissionStatus.DISPUTED))
    return list(result)


@router.get("/stats")
async def revenue_stats(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    total_commission = await db.scalar(
        select(func.coalesce(func.sum(Transaction.commission_fcfa), 0)).where(
            Transaction.status == TransactionStatus.RELEASED
        )
    )
    total_missions = await db.scalar(select(func.count()).select_from(Mission))
    return {
        "commission_totale_fcfa": int(total_commission or 0),
        "missions_totales": int(total_missions or 0),
    }


@router.get("/kyc/pending", response_model=list[UserRead])
async def list_pending_kyc(db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.scalars(select(User).where(User.kyc_status == KycStatus.PENDING))
    return list(result)


@router.get("/kyc/{user_id}/document-url")
async def get_kyc_document_url(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Retourne une URL signée temporaire (2 min) vers le document KYC, jamais d'URL publique."""
    target_user = await db.get(User, user_id)
    if target_user is None or not target_user.kyc_document_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun document KYC pour cet utilisateur")
    url = await create_signed_url(path=target_user.kyc_document_path)
    return {"url": url}


@router.post("/kyc/{user_id}/approve", response_model=UserRead)
async def approve_kyc(
    user_id: uuid.UUID,
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> User:
    target_user = await db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    target_user.kyc_status = KycStatus.APPROVED
    target_user.is_verified_provider = True
    db.add(
        AuditLog(actor_id=current_admin.id, action="kyc_approved", target_type="user", target_id=str(target_user.id))
    )
    await db.commit()
    await db.refresh(target_user)
    return target_user


@router.post("/kyc/{user_id}/reject", response_model=UserRead)
async def reject_kyc(
    user_id: uuid.UUID,
    payload: KycRejectRequest,
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> User:
    target_user = await db.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    target_user.kyc_status = KycStatus.REJECTED
    target_user.is_verified_provider = False
    db.add(
        AuditLog(
            actor_id=current_admin.id,
            action="kyc_rejected",
            target_type="user",
            target_id=str(target_user.id),
            extra_data={"reason": payload.reason},
        )
    )
    await db.commit()
    await db.refresh(target_user)
    return target_user
