import hashlib
import hmac
import json

from app.core.config import get_settings


def _sign(body: bytes) -> str:
    secret = get_settings().paydunia_webhook_secret
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_missing_signature_rejected(client):
    response = client.post(
        "/api/payments/webhook/paydunia", json={"reference": "unknown", "status": "success"}
    )
    assert response.status_code == 422


def test_webhook_invalid_signature_rejected(client):
    body = json.dumps({"reference": "unknown", "status": "success"}).encode()
    response = client.post(
        "/api/payments/webhook/paydunia",
        content=body,
        headers={"Content-Type": "application/json", "X-Paydunia-Signature": "0" * 64},
    )
    assert response.status_code == 401


def test_webhook_unknown_transaction_rejected_even_with_valid_signature(client):
    body = json.dumps({"reference": "does-not-exist", "status": "success"}).encode()
    response = client.post(
        "/api/payments/webhook/paydunia",
        content=body,
        headers={"Content-Type": "application/json", "X-Paydunia-Signature": _sign(body)},
    )
    assert response.status_code == 404
