from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.boost import Boost, BoostStatus, BoostTargetType
from app.models.mission import Mission
from app.models.user import User, UserRole
from app.schemas.boost import BoostCreate, BoostRead

router = APIRouter(prefix="/api/boosts", tags=["boosts"])
settings = get_settings()


@router.post("", response_model=BoostRead, status_code=status.HTTP_201_CREATED)
async def request_boost(
    payload: BoostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Boost:
    """Demande de mise en avant (48h) d'une mission ou d'un profil prestataire.

    Reste en statut "pending_payment" jusqu'à confirmation du paiement (validation
    manuelle admin en attendant l'intégration complète de l'initiation Paydunia,
    cf. api/routes/payments.py).
    """
    if payload.target_type == BoostTargetType.MISSION:
        mission = await db.get(Mission, payload.target_id)
        if mission is None or mission.client_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission introuvable")
    else:
        if current_user.role != UserRole.PROVIDER or payload.target_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez booster que votre propre profil prestataire",
            )

    boost = Boost(
        owner_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        amount_fcfa=settings.boost_price_fcfa,
        status=BoostStatus.PENDING_PAYMENT,
    )
    db.add(boost)
    await db.commit()
    await db.refresh(boost)
    return boost


@router.get("/mine", response_model=list[BoostRead])
async def list_my_boosts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Boost]:
    result = await db.scalars(
        select(Boost).where(Boost.owner_id == current_user.id).order_by(Boost.id.desc())
    )
    return list(result)
