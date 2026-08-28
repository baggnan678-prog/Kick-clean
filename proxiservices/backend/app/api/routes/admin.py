from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.mission import Mission, MissionStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import UserRole
from app.schemas.mission import MissionRead

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
