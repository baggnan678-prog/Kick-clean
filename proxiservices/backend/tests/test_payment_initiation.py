from tests.conftest import auth_headers, login, register_user


def _setup_accepted_mission(client):
    register_user(client, email="client@example.com", password="clientpass1", role="client")
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    client_token = login(client, email="client@example.com", password="clientpass1")
    provider_token = login(client, email="provider@example.com", password="providerpass1")
    admin_token = login(client, email="admin@example.com", password="adminpass1")

    category_id = client.post(
        "/api/services/categories",
        json={"name": "Reparation", "slug": "reparation"},
        headers=auth_headers(admin_token),
    ).json()["id"]

    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Reparation de climatiseur",
            "description": "Le climatiseur ne refroidit plus depuis deux jours",
            "budget_fcfa": 20000,
            "neighborhood": "Patte d'Oie",
        },
        headers=auth_headers(client_token),
    ).json()

    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 18000},
        headers=auth_headers(provider_token),
    ).json()

    client.post(
        f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept",
        headers=auth_headers(client_token),
    )

    return mission, client_token, provider_token


async def _fake_initiate_payment(*, amount_fcfa: int, description: str) -> dict:
    return {"payment_url": "https://pay.paydunia.example/checkout/abc123", "provider_reference": "paydunia-ref-abc123"}


def test_client_can_initiate_payment(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.payments.initiate_payment", _fake_initiate_payment)
    mission, client_token, _ = _setup_accepted_mission(client)

    response = client.post(f"/api/payments/missions/{mission['id']}/initiate", headers=auth_headers(client_token))
    assert response.status_code == 200, response.text
    assert response.json()["payment_url"] == "https://pay.paydunia.example/checkout/abc123"


def test_provider_cannot_initiate_payment(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.payments.initiate_payment", _fake_initiate_payment)
    mission, _, provider_token = _setup_accepted_mission(client)

    response = client.post(f"/api/payments/missions/{mission['id']}/initiate", headers=auth_headers(provider_token))
    assert response.status_code == 403


def test_cannot_initiate_payment_for_mission_without_pending_transaction(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.payments.initiate_payment", _fake_initiate_payment)
    register_user(client, email="client2@example.com", password="clientpass1", role="client")
    register_user(client, email="admin2@example.com", password="adminpass1", role="admin")
    client_token = login(client, email="client2@example.com", password="clientpass1")
    admin_token = login(client, email="admin2@example.com", password="adminpass1")

    category_id = client.post(
        "/api/services/categories",
        json={"name": "Autre categorie", "slug": "autre-categorie"},
        headers=auth_headers(admin_token),
    ).json()["id"]
    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Mission sans devis accepte",
            "description": "Aucun prestataire n'a encore ete choisi pour ce besoin",
            "budget_fcfa": 3000,
            "neighborhood": "Secteur 15",
        },
        headers=auth_headers(client_token),
    ).json()

    response = client.post(f"/api/payments/missions/{mission['id']}/initiate", headers=auth_headers(client_token))
    assert response.status_code == 400


def test_initiate_payment_without_api_key_returns_503(client):
    # PAYDUNIA_API_KEY n'est pas configurée dans l'environnement de test : la
    # garde de configuration doit se déclencher avant tout appel réseau.
    mission, client_token, _ = _setup_accepted_mission(client)

    response = client.post(f"/api/payments/missions/{mission['id']}/initiate", headers=auth_headers(client_token))
    assert response.status_code == 503


def test_webhook_updates_transaction_after_initiation(client, monkeypatch):
    import hashlib
    import hmac
    import json

    from app.core.config import get_settings

    monkeypatch.setattr("app.api.routes.payments.initiate_payment", _fake_initiate_payment)
    mission, client_token, _ = _setup_accepted_mission(client)
    client.post(f"/api/payments/missions/{mission['id']}/initiate", headers=auth_headers(client_token))

    secret = get_settings().paydunia_webhook_secret
    body = json.dumps({"reference": "paydunia-ref-abc123", "status": "success"}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/payments/webhook/paydunia",
        content=body,
        headers={"Content-Type": "application/json", "X-Paydunia-Signature": signature},
    )
    assert response.status_code == 204
