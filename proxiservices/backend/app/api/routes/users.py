import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core.storage import upload_kyc_document
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import KycStatus, User, UserRole
from app.schemas.user import UserRead

router = APIRouter(prefix="/api/users", tags=["users"])

ALLOWED_KYC_CONTENT_TYPES = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}
MAX_KYC_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 Mo


@router.get("/me", response_model=UserRead)
async def read_current_user(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/me/kyc-document", response_model=UserRead, status_code=status.HTTP_202_ACCEPTED)
async def upload_my_kyc_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.PROVIDER)),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Un prestataire soumet une pièce d'identité pour vérification (badge « Vérifié »)."""
    if file.content_type not in ALLOWED_KYC_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format non accepté (PDF, JPEG ou PNG uniquement)",
        )

    content = await file.read()
    if len(content) > MAX_KYC_DOCUMENT_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document trop volumineux (5 Mo maximum)")

    extension = ALLOWED_KYC_CONTENT_TYPES[file.content_type]
    path = f"{current_user.id}/{uuid.uuid4()}.{extension}"

    await upload_kyc_document(path=path, content=content, content_type=file.content_type)

    current_user.kyc_document_path = path
    current_user.kyc_status = KycStatus.PENDING
    db.add(
        AuditLog(
            actor_id=current_user.id,
            action="kyc_document_submitted",
            target_type="user",
            target_id=str(current_user.id),
        )
    )
    await db.commit()
    await db.refresh(current_user)
    return current_user
