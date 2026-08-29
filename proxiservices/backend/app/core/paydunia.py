"""Intégration Paydunia — initiation de paiement.

IMPORTANT : les chemins d'API, noms de champs et format de réponse ci-dessous
suivent les conventions habituelles des agrégateurs de paiement Mobile Money,
mais n'ont PAS pu être vérifiés contre la documentation réelle de l'API
Paydunia (nécessite un compte marchand). Avant la mise en production, il
faudra ajuster `_build_request_payload` et `_extract_payment_url` d'après la
documentation fournie par Paydunia à la création du compte marchand.
"""

import uuid

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings

settings = get_settings()


def _require_paydunia_configured() -> None:
    if not settings.paydunia_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le paiement Paydunia n'est pas configuré (PAYDUNIA_API_KEY manquante)",
        )


def _build_request_payload(*, amount_fcfa: int, reference: str, description: str) -> dict:
    return {
        "amount": amount_fcfa,
        "currency": "XOF",
        "reference": reference,
        "description": description,
        "notify_url": settings.paydunia_webhook_url,
        "return_url": settings.paydunia_return_url,
    }


def _extract_payment_url(response_data: dict) -> tuple[str, str]:
    """Retourne (payment_url, provider_reference) à partir de la réponse Paydunia."""
    payment_url = response_data.get("payment_url") or response_data.get("checkout_url")
    provider_reference = response_data.get("reference") or response_data.get("id")
    if not payment_url or not provider_reference:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Réponse Paydunia inattendue : payment_url ou reference manquant",
        )
    return payment_url, provider_reference


async def initiate_payment(*, amount_fcfa: int, description: str) -> dict:
    """Initie un paiement Paydunia et retourne {"payment_url", "provider_reference"}.

    `reference` est généré côté ProxiServices pour pouvoir retrouver la
    transaction lors de la réception du webhook de confirmation
    (cf. api/routes/payments.py::paydunia_webhook).
    """
    _require_paydunia_configured()

    reference = f"proxiservices-{uuid.uuid4()}"
    payload = _build_request_payload(amount_fcfa=amount_fcfa, reference=reference, description=description)
    headers = {"Authorization": f"Bearer {settings.paydunia_api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30) as http_client:
        response = await http_client.post(f"{settings.paydunia_base_url}/v1/payments", json=payload, headers=headers)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Échec de l'initiation du paiement Paydunia : {response.text}",
        )

    payment_url, provider_reference = _extract_payment_url(response.json())
    return {"payment_url": payment_url, "provider_reference": provider_reference}
