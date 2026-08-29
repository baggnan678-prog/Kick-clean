from tests.conftest import auth_headers, login, register_user


def _setup_provider_and_admin(client):
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    provider_token = login(client, email="provider@example.com", password="providerpass1")
    admin_token = login(client, email="admin@example.com", password="adminpass1")
    provider_me = client.get("/api/users/me", headers=auth_headers(provider_token)).json()
    return provider_me, provider_token, admin_token


# --- Abonnements ---

def test_provider_starts_on_free_plan(client):
    _, provider_token, _ = _setup_provider_and_admin(client)
    response = client.get("/api/subscriptions/me", headers=auth_headers(provider_token))
    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["status"] == "active"


def test_admin_can_activate_and_cancel_pro_subscription(client):
    provider, provider_token, admin_token = _setup_provider_and_admin(client)

    activate_response = client.post(
        f"/api/admin/subscriptions/{provider['id']}/activate-pro",
        json={"duration_days": 30},
        headers=auth_headers(admin_token),
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["plan"] == "pro"
    assert activate_response.json()["expires_at"] is not None

    mine = client.get("/api/subscriptions/me", headers=auth_headers(provider_token)).json()
    assert mine["plan"] == "pro"

    cancel_response = client.post(
        f"/api/admin/subscriptions/{provider['id']}/cancel", headers=auth_headers(admin_token)
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["plan"] == "free"
    assert cancel_response.json()["status"] == "cancelled"


def test_non_admin_cannot_activate_subscription(client):
    provider, provider_token, _ = _setup_provider_and_admin(client)
    response = client.post(
        f"/api/admin/subscriptions/{provider['id']}/activate-pro",
        json={"duration_days": 30},
        headers=auth_headers(provider_token),
    )
    assert response.status_code == 403


# --- Boosts ---

def test_provider_can_request_boost_on_own_profile(client):
    provider, provider_token, admin_token = _setup_provider_and_admin(client)

    response = client.post(
        "/api/boosts",
        json={"target_type": "provider_profile", "target_id": provider["id"]},
        headers=auth_headers(provider_token),
    )
    assert response.status_code == 201
    boost = response.json()
    assert boost["status"] == "pending_payment"
    assert boost["amount_fcfa"] == 500

    mine = client.get("/api/boosts/mine", headers=auth_headers(provider_token)).json()
    assert len(mine) == 1

    activate_response = client.post(
        f"/api/admin/boosts/{boost['id']}/activate", headers=auth_headers(admin_token)
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["status"] == "active"
    assert activate_response.json()["starts_at"] is not None


def test_provider_cannot_boost_someone_elses_profile(client):
    register_user(client, email="provider2@example.com", password="providerpass1", role="provider")
    provider, provider_token, _ = _setup_provider_and_admin(client)
    other_provider_token = login(client, email="provider2@example.com", password="providerpass1")

    response = client.post(
        "/api/boosts",
        json={"target_type": "provider_profile", "target_id": provider["id"]},
        headers=auth_headers(other_provider_token),
    )
    assert response.status_code == 403


def test_cannot_activate_boost_twice(client):
    provider, provider_token, admin_token = _setup_provider_and_admin(client)
    boost = client.post(
        "/api/boosts",
        json={"target_type": "provider_profile", "target_id": provider["id"]},
        headers=auth_headers(provider_token),
    ).json()

    client.post(f"/api/admin/boosts/{boost['id']}/activate", headers=auth_headers(admin_token))
    second_attempt = client.post(f"/api/admin/boosts/{boost['id']}/activate", headers=auth_headers(admin_token))
    assert second_attempt.status_code == 400


# --- Modération des annonces ---

def test_admin_can_moderate_mission(client):
    register_user(client, email="client@example.com", password="clientpass1", role="client")
    _, _, admin_token = _setup_provider_and_admin(client)
    client_token = login(client, email="client@example.com", password="clientpass1")

    category_id = client.post(
        "/api/services/categories",
        json={"name": "Déménagement", "slug": "demenagement"},
        headers=auth_headers(admin_token),
    ).json()["id"]

    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Annonce suspecte à modérer",
            "description": "Contenu qui enfreint les règles de la plateforme",
            "budget_fcfa": 1000,
            "neighborhood": "Somewhere",
        },
        headers=auth_headers(client_token),
    ).json()

    all_missions = client.get("/api/admin/missions", headers=auth_headers(admin_token)).json()
    assert len(all_missions) == 1

    moderate_response = client.post(
        f"/api/admin/missions/{mission['id']}/moderate",
        json={"reason": "Contenu non conforme aux règles"},
        headers=auth_headers(admin_token),
    )
    assert moderate_response.status_code == 200
    assert moderate_response.json()["status"] == "cancelled"

    # Une annonce annulée ne doit plus apparaître dans la liste publique des missions ouvertes.
    assert client.get("/api/missions").json() == []
