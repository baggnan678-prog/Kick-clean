import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def _require_storage_configured() -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le stockage des documents KYC n'est pas configuré (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY manquants)",
        )


async def upload_kyc_document(*, path: str, content: bytes, content_type: str) -> str:
    """Envoie un document au bucket privé Supabase Storage dédié au KYC. Retourne le chemin stocké."""
    _require_storage_configured()

    url = f"{settings.supabase_url}/storage/v1/object/{settings.supabase_kyc_bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }

    async with httpx.AsyncClient(timeout=30) as http_client:
        response = await http_client.post(url, headers=headers, content=content)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Échec de l'envoi du document vers Supabase Storage : {response.text}",
        )
    return path


async def create_signed_url(*, path: str, expires_in_seconds: int = 120) -> str:
    """Génère une URL signée temporaire pour qu'un admin puisse consulter un document privé."""
    _require_storage_configured()

    url = f"{settings.supabase_url}/storage/v1/object/sign/{settings.supabase_kyc_bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as http_client:
        response = await http_client.post(url, headers=headers, json={"expiresIn": expires_in_seconds})

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Échec de la génération de l'URL signée : {response.text}",
        )

    signed_path = response.json()["signedURL"]
    return f"{settings.supabase_url}/storage/v1{signed_path}"
