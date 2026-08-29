import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.notifications import notification_service
from app.core.storage import create_signed_url
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.boost import Boost, BoostStatus
from app.models.mission import Mission, MissionStatus
from app.models.subscription import ProviderSubscription, SubscriptionPlan, SubscriptionStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import KycStatus, User, UserRole
from app.schemas.boost import BoostRead
from app.schemas.mission import DisputeResolve, MissionModerate, MissionRead
from app.schemas.subscription import SubscriptionActivate, SubscriptionRead
from app.schemas.user import KycRejectRequest, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role(UserRole.ADMIN))])


@router.get("/disputes", response_model=list[MissionRead])
async def list_disputes(db: AsyncSession = Depends(get_db)) -> list[Mission]:
    result = await db.scalars(select(Mission).where(Mission.status == MissionStatus.DISPUTED))
    return list(result)


@router.post("/disputes/{mission_id}/resolve", response_model=MissionRead)
async def resolve_dispute(
    mission_id: uuid.UUID,
    payload: DisputeResolve,
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Mission:
    """Tranche un litige : libère les fonds au prestataire, ou rembourse le client."""
    mission = await db.get(Mission, mission_id)
    if mission is None or mission.status != MissionStatus.DISPUTED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aucun litige ouvert pour cette mission")

    transaction = await db.scalar(select(Transaction).where(Transaction.mission_id == mission.id))

    if payload.resolution == "release":
        if transaction is not None and transaction.status == TransactionStatus.HELD_IN_ESCROW:
            transaction.status = TransactionStatus.RELEASED
        mission.status = MissionStatus.COMPLETED
    else:
        if transaction is not None and transaction.status == TransactionStatus.HELD_IN_ESCROW:
            transaction.status = TransactionStatus.REFUNDED
        mission.status = MissionStatus.CANCELLED

    db.add(
        AuditLog(
            actor_id=current_admin.id,
            action="dispute_resolved",
            target_type="mission",
            target_id=str(mission.id),
            extra_data={"resolution": payload.resolution, "admin_note": payload.admin_note},
        )
    )

    await db.commit()
    await db.refresh(mission)

    resolution_label = "les fonds ont été libérés au prestataire" if payload.resolution == "release" else "le client a été remboursé"
    for party_id in (mission.client_id, mission.provider_id):
        if party_id is None:
            continue
        party = await db.get(User, party_id)
        if party is not None:
            await notification_service.notify_user(
                party,
                subject="Litige résolu",
                body=f"Le litige sur « {mission.title} » a été tranché : {resolution_label}.",
            )
    return mission


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

    await notification_service.notify_user(
        target_user,
        subject="Identité vérifiée",
        body="Votre pièce d'identité a été validée : le badge « Vérifié » est désormais actif sur votre profil.",
    )
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

    await notification_service.notify_user(
        target_user,
        subject="Document KYC refusé",
        body=f"Votre pièce d'identité a été refusée : {payload.reason}. Merci d'en soumettre une nouvelle.",
    )
    return target_user


@router.get("/missions", response_model=list[MissionRead])
async def list_all_missions(db: AsyncSession = Depends(get_db)) -> list[Mission]:
    """Vue de modération : toutes les missions, tous statuts confondus."""
    result = await db.scalars(select(Mission).order_by(Mission.created_at.desc()))
    return list(result)


@router.post("/missions/{mission_id}/moderate", response_model=MissionRead)
async def moderate_mission(
    mission_id: uuid.UUID,
    payload: MissionModerate,
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Mission:
    """Retire une annonce inappropriée (spam, contenu interdit...) en l'annulant."""
    mission = await db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission introuvable")
    if mission.status in (MissionStatus.COMPLETED, MissionStatus.CANCELLED):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette mission ne peut plus être modérée")

    mission.status = MissionStatus.CANCELLED
    db.add(
        AuditLog(
            actor_id=current_admin.id,
            action="mission_moderated",
            target_type="mission",
            target_id=str(mission.id),
            extra_data={"reason": payload.reason},
        )
    )
    await db.commit()
    await db.refresh(mission)
    return mission


@router.get("/subscriptions", response_model=list[SubscriptionRead])
async def list_subscriptions(db: AsyncSession = Depends(get_db)) -> list[ProviderSubscription]:
    result = await db.scalars(select(ProviderSubscription))
    return list(result)


@router.post("/subscriptions/{provider_id}/activate-pro", response_model=SubscriptionRead)
async def activate_pro_subscription(
    provider_id: uuid.UUID,
    payload: SubscriptionActivate,
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ProviderSubscription:
    """Active manuellement l'abonnement Pro (en attendant l'intégration complète du
    paiement récurrent Paydunia) après confirmation d'un paiement reçu."""
    provider = await db.get(User, provider_id)
    if provider is None or provider.role != UserRole.PROVIDER:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prestataire introuvable")

    subscription = await db.scalar(
        select(ProviderSubscription).where(ProviderSubscription.provider_id == provider_id)
    )
    if subscription is None:
        subscription = ProviderSubscription(provider_id=provider_id)
        db.add(subscription)

    subscription.plan = SubscriptionPlan.PRO
    subscription.status = SubscriptionStatus.ACTIVE
    subscription.expires_at = datetime.now(timezone.utc) + timedelta(days=payload.duration_days)

    db.add(
        AuditLog(
            actor_id=current_admin.id,
            action="subscription_pro_activated",
            target_type="user",
            target_id=str(provider_id),
            extra_data={"duration_days": payload.duration_days},
        )
    )
    await db.commit()
    await db.refresh(subscription)

    await notification_service.notify_user(
        provider,
        subject="Abonnement Pro activé",
        body=f"Votre abonnement Pro est actif pour {payload.duration_days} jours : badge « Vérifié », priorité de recherche et devis illimités.",
    )
    return subscription


@router.post("/subscriptions/{provider_id}/cancel", response_model=SubscriptionRead)
async def cancel_subscription(
    provider_id: uuid.UUID,
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> ProviderSubscription:
    subscription = await db.scalar(
        select(ProviderSubscription).where(ProviderSubscription.provider_id == provider_id)
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable")

    subscription.plan = SubscriptionPlan.FREE
    subscription.status = SubscriptionStatus.CANCELLED
    db.add(
        AuditLog(
            actor_id=current_admin.id,
            action="subscription_cancelled",
            target_type="user",
            target_id=str(provider_id),
        )
    )
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.get("/boosts", response_model=list[BoostRead])
async def list_boosts(db: AsyncSession = Depends(get_db)) -> list[Boost]:
    result = await db.scalars(select(Boost).order_by(Boost.id.desc()))
    return list(result)


@router.post("/boosts/{boost_id}/activate", response_model=BoostRead)
async def activate_boost(
    boost_id: uuid.UUID,
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
) -> Boost:
    """Active un boost (48h) après confirmation manuelle du paiement de 500 FCFA."""
    boost = await db.get(Boost, boost_id)
    if boost is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boost introuvable")
    if boost.status != BoostStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce boost n'est pas en attente de paiement")

    now = datetime.now(timezone.utc)
    boost.status = BoostStatus.ACTIVE
    boost.starts_at = now
    boost.ends_at = now + timedelta(hours=48)

    db.add(
        AuditLog(
            actor_id=current_admin.id,
            action="boost_activated",
            target_type="boost",
            target_id=str(boost.id),
        )
    )
    await db.commit()
    await db.refresh(boost)

    owner = await db.get(User, boost.owner_id)
    if owner is not None:
        await notification_service.notify_user(
            owner,
            subject="Boost activé",
            body="Votre mise en avant de 48h est désormais active.",
        )
    return boost
