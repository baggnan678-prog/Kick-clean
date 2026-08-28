import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.config import get_settings
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.mission import Mission, MissionStatus, Quote, QuoteStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User, UserRole
from app.schemas.mission import MissionCreate, MissionRead, QuoteCreate, QuoteRead

router = APIRouter(prefix="/api/missions", tags=["missions"])
settings = get_settings()


@router.post("", response_model=MissionRead, status_code=status.HTTP_201_CREATED)
async def create_mission(
    payload: MissionCreate,
    current_user: User = Depends(require_role(UserRole.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> Mission:
    mission = Mission(client_id=current_user.id, **payload.model_dump())
    db.add(mission)
    await db.commit()
    await db.refresh(mission)
    return mission


@router.get("", response_model=list[MissionRead])
async def list_open_missions(db: AsyncSession = Depends(get_db)) -> list[Mission]:
    result = await db.scalars(
        select(Mission).where(Mission.status == MissionStatus.OPEN).order_by(Mission.created_at.desc())
    )
    return list(result)


@router.get("/{mission_id}", response_model=MissionRead)
async def get_mission(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Mission:
    mission = await db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission introuvable")
    return mission


@router.post("/{mission_id}/quotes", response_model=QuoteRead, status_code=status.HTTP_201_CREATED)
async def submit_quote(
    mission_id: uuid.UUID,
    payload: QuoteCreate,
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> Quote:
    mission = await db.get(Mission, mission_id)
    if mission is None or mission.status != MissionStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette mission n'accepte plus de devis")

    quote = Quote(mission_id=mission_id, provider_id=current_user.id, **payload.model_dump())
    db.add(quote)
    mission.status = MissionStatus.QUOTED
    await db.commit()
    await db.refresh(quote)
    return quote


@router.post("/{mission_id}/quotes/{quote_id}/accept", response_model=MissionRead)
async def accept_quote(
    mission_id: uuid.UUID,
    quote_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> Mission:
    mission = await db.get(Mission, mission_id)
    if mission is None or mission.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission introuvable")

    quote = await db.get(Quote, quote_id)
    if quote is None or quote.mission_id != mission_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Devis introuvable")

    quote.status = QuoteStatus.ACCEPTED
    mission.status = MissionStatus.ACCEPTED
    mission.provider_id = quote.provider_id

    # La commission (7 à 10% selon le cahier des charges) est calculée dès l'acceptation
    # du devis ; les fonds restent en séquestre jusqu'à la validation finale du client.
    commission = round(quote.amount_fcfa * settings.commission_rate)
    transaction = Transaction(
        mission_id=mission.id,
        client_id=current_user.id,
        provider_id=quote.provider_id,
        amount_fcfa=quote.amount_fcfa,
        commission_fcfa=commission,
        status=TransactionStatus.PENDING,
    )
    db.add(transaction)
    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="quote_accepted",
            target_type="mission",
            target_id=str(mission.id),
        )
    )

    await db.commit()
    await db.refresh(mission)
    return mission


@router.post("/{mission_id}/complete", response_model=MissionRead)
async def complete_mission(
    mission_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.CLIENT)),
    db: AsyncSession = Depends(get_db),
) -> Mission:
    mission = await db.get(Mission, mission_id)
    if mission is None or mission.client_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission introuvable")
    if mission.status not in (MissionStatus.ACCEPTED, MissionStatus.IN_PROGRESS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cette mission ne peut pas être clôturée")

    transaction = await db.scalar(select(Transaction).where(Transaction.mission_id == mission.id))
    if transaction is not None and transaction.status == TransactionStatus.HELD_IN_ESCROW:
        # Libération des fonds au prestataire uniquement après validation du client (séquestre).
        transaction.status = TransactionStatus.RELEASED

    mission.status = MissionStatus.COMPLETED
    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="mission_completed",
            target_type="mission",
            target_id=str(mission.id),
        )
    )

    await db.commit()
    await db.refresh(mission)
    return mission
