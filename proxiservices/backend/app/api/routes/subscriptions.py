from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.db.session import get_db
from app.models.subscription import ProviderSubscription
from app.models.user import User, UserRole
from app.schemas.subscription import SubscriptionRead

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/me", response_model=SubscriptionRead)
async def read_my_subscription(
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> ProviderSubscription:
    subscription = await db.scalar(
        select(ProviderSubscription).where(ProviderSubscription.provider_id == current_user.id)
    )
    if subscription is None:
        # Chaque prestataire démarre sur le plan gratuit ; la ligne est créée
        # paresseusement à la première consultation.
        subscription = ProviderSubscription(provider_id=current_user.id)
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
    return subscription
