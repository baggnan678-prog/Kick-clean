from app.core.notifications import notification_service
from tests.conftest import auth_headers, login, register_user


def _spy_notifications(monkeypatch):
    calls = []

    async def fake_notify_user(user, *, subject, body):
        calls.append((user.email, subject))

    monkeypatch.setattr(notification_service, "notify_user", fake_notify_user)
    return calls


def _setup_client_provider_admin(client):
    register_user(client, email="client@example.com", password="clientpass1", role="client")
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    return (
        login(client, email="client@example.com", password="clientpass1"),
        login(client, email="provider@example.com", password="providerpass1"),
        login(client, email="admin@example.com", password="adminpass1"),
    )


def _create_accepted_mission(client, client_token, provider_token, admin_token):
    category_id = client.post(
        "/api/services/categories",
        json={"name": "Cat", "slug": "cat"},
        headers=auth_headers(admin_token),
    ).json()["id"]
    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Mission notifiee",
            "description": "Description suffisamment longue pour valider",
            "budget_fcfa": 5000,
            "neighborhood": "Quartier",
        },
        headers=auth_headers(client_token),
    ).json()
    return mission


def test_quote_submission_notifies_client(client, monkeypatch):
    calls = _spy_notifications(monkeypatch)
    client_token, provider_token, admin_token = _setup_client_provider_admin(client)
    mission = _create_accepted_mission(client, client_token, provider_token, admin_token)

    client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 4500},
        headers=auth_headers(provider_token),
    )

    assert ("client@example.com", "Nouveau devis reçu") in calls


def test_quote_acceptance_notifies_provider(client, monkeypatch):
    calls = _spy_notifications(monkeypatch)
    client_token, provider_token, admin_token = _setup_client_provider_admin(client)
    mission = _create_accepted_mission(client, client_token, provider_token, admin_token)
    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 4500},
        headers=auth_headers(provider_token),
    ).json()

    client.post(
        f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept",
        headers=auth_headers(client_token),
    )

    assert ("provider@example.com", "Votre devis a été accepté") in calls


def test_mission_completion_notifies_provider(client, monkeypatch):
    client_token, provider_token, admin_token = _setup_client_provider_admin(client)
    mission = _create_accepted_mission(client, client_token, provider_token, admin_token)
    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 4500},
        headers=auth_headers(provider_token),
    ).json()
    client.post(f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept", headers=auth_headers(client_token))

    calls = _spy_notifications(monkeypatch)
    client.post(f"/api/missions/{mission['id']}/complete", headers=auth_headers(client_token))

    assert ("provider@example.com", "Mission clôturée, fonds libérés") in calls


def test_dispute_opened_notifies_all_admins(client, monkeypatch):
    client_token, provider_token, admin_token = _setup_client_provider_admin(client)
    register_user(client, email="admin2@example.com", password="adminpass1", role="admin")
    mission = _create_accepted_mission(client, client_token, provider_token, admin_token)
    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 4500},
        headers=auth_headers(provider_token),
    ).json()
    client.post(f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept", headers=auth_headers(client_token))

    calls = _spy_notifications(monkeypatch)
    client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Probleme de qualite du travail rendu"},
        headers=auth_headers(client_token),
    )

    notified_emails = {email for email, subject in calls if subject == "Nouveau litige à examiner"}
    assert notified_emails == {"admin@example.com", "admin2@example.com"}


def test_dispute_resolution_notifies_both_parties(client, monkeypatch):
    client_token, provider_token, admin_token = _setup_client_provider_admin(client)
    mission = _create_accepted_mission(client, client_token, provider_token, admin_token)
    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 4500},
        headers=auth_headers(provider_token),
    ).json()
    client.post(f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept", headers=auth_headers(client_token))
    client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Probleme de qualite du travail rendu"},
        headers=auth_headers(client_token),
    )

    calls = _spy_notifications(monkeypatch)
    client.post(
        f"/api/admin/disputes/{mission['id']}/resolve",
        json={"resolution": "refund"},
        headers=auth_headers(admin_token),
    )

    notified = {(email, subject) for email, subject in calls}
    assert ("client@example.com", "Litige résolu") in notified
    assert ("provider@example.com", "Litige résolu") in notified


def test_kyc_approval_and_rejection_notify_provider(client, monkeypatch):
    import io

    async def fake_upload(*, path, content, content_type):
        return path

    monkeypatch.setattr("app.api.routes.users.upload_kyc_document", fake_upload)
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    provider_token = login(client, email="provider@example.com", password="providerpass1")
    admin_token = login(client, email="admin@example.com", password="adminpass1")
    provider = client.get("/api/users/me", headers=auth_headers(provider_token)).json()

    client.post(
        "/api/users/me/kyc-document",
        files={"file": ("id.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        headers=auth_headers(provider_token),
    )

    calls = _spy_notifications(monkeypatch)
    client.post(f"/api/admin/kyc/{provider['id']}/approve", headers=auth_headers(admin_token))
    assert ("provider@example.com", "Identité vérifiée") in calls

    calls.clear()
    client.post(
        f"/api/admin/kyc/{provider['id']}/reject",
        json={"reason": "Document illisible"},
        headers=auth_headers(admin_token),
    )
    assert ("provider@example.com", "Document KYC refusé") in calls


def test_subscription_activation_notifies_provider(client, monkeypatch):
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    provider_token = login(client, email="provider@example.com", password="providerpass1")
    admin_token = login(client, email="admin@example.com", password="adminpass1")
    provider = client.get("/api/users/me", headers=auth_headers(provider_token)).json()

    calls = _spy_notifications(monkeypatch)
    client.post(
        f"/api/admin/subscriptions/{provider['id']}/activate-pro",
        json={"duration_days": 30},
        headers=auth_headers(admin_token),
    )
    assert ("provider@example.com", "Abonnement Pro activé") in calls


def test_boost_activation_notifies_owner(client, monkeypatch):
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    provider_token = login(client, email="provider@example.com", password="providerpass1")
    admin_token = login(client, email="admin@example.com", password="adminpass1")
    provider = client.get("/api/users/me", headers=auth_headers(provider_token)).json()

    boost = client.post(
        "/api/boosts",
        json={"target_type": "provider_profile", "target_id": provider["id"]},
        headers=auth_headers(provider_token),
    ).json()

    calls = _spy_notifications(monkeypatch)
    client.post(f"/api/admin/boosts/{boost['id']}/activate", headers=auth_headers(admin_token))
    assert ("provider@example.com", "Boost activé") in calls
