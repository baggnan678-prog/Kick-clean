from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.session import get_db
from app.models.service import ServiceCategory
from app.models.user import UserRole
from app.schemas.service import ServiceCategoryCreate, ServiceCategoryRead

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("/categories", response_model=list[ServiceCategoryRead])
async def list_categories(db: AsyncSession = Depends(get_db)) -> list[ServiceCategory]:
    result = await db.scalars(select(ServiceCategory).order_by(ServiceCategory.name))
    return list(result)


@router.post(
    "/categories",
    response_model=ServiceCategoryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
async def create_category(payload: ServiceCategoryCreate, db: AsyncSession = Depends(get_db)) -> ServiceCategory:
    existing = await db.scalar(select(ServiceCategory).where(ServiceCategory.slug == payload.slug))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cette catégorie existe déjà")

    category = ServiceCategory(**payload.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category
