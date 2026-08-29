from tests.conftest import auth_headers, login, register_user


def _create_category(client, admin_token, slug="plomberie", name="Plomberie"):
    response = client.post(
        "/api/services/categories",
        json={"name": name, "slug": slug, "description": "Dépannage plomberie"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _setup_users(client):
    register_user(client, email="client@example.com", password="clientpass1", role="client")
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    return (
        login(client, email="client@example.com", password="clientpass1"),
        login(client, email="provider@example.com", password="providerpass1"),
        login(client, email="admin@example.com", password="adminpass1"),
    )


def test_full_mission_lifecycle(client):
    client_token, provider_token, admin_token = _setup_users(client)
    category_id = _create_category(client, admin_token)

    mission_response = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Fuite d'eau urgente",
            "description": "Fuite sous l'évier de la cuisine, besoin d'intervention rapide",
            "budget_fcfa": 15000,
            "neighborhood": "Ouaga 2000",
        },
        headers=auth_headers(client_token),
    )
    assert mission_response.status_code == 201
    mission = mission_response.json()
    assert mission["status"] == "open"

    open_missions = client.get("/api/missions").json()
    assert len(open_missions) == 1

    quote_response = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 12000, "message": "Je peux venir demain matin"},
        headers=auth_headers(provider_token),
    )
    assert quote_response.status_code == 201
    quote = quote_response.json()

    accept_response = client.post(
        f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept",
        headers=auth_headers(client_token),
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["status"] == "accepted"

    complete_response = client.post(
        f"/api/missions/{mission['id']}/complete",
        headers=auth_headers(client_token),
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    stats = client.get("/api/admin/stats", headers=auth_headers(admin_token)).json()
    assert stats["missions_totales"] == 1


def test_provider_cannot_create_mission(client):
    _, provider_token, admin_token = _setup_users(client)
    category_id = _create_category(client, admin_token)

    response = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Test interdit",
            "description": "Un prestataire ne doit pas pouvoir publier de besoin",
            "budget_fcfa": 1000,
            "neighborhood": "Quartier X",
        },
        headers=auth_headers(provider_token),
    )
    assert response.status_code == 403


def test_non_admin_cannot_create_category(client):
    client_token, _, _ = _setup_users(client)
    response = client.post(
        "/api/services/categories",
        json={"name": "Autre", "slug": "autre"},
        headers=auth_headers(client_token),
    )
    assert response.status_code == 403


def test_quote_rejected_when_mission_not_open(client):
    client_token, provider_token, admin_token = _setup_users(client)
    category_id = _create_category(client, admin_token)

    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Réparation électrique",
            "description": "Panne de courant dans tout l'appartement",
            "budget_fcfa": 8000,
            "neighborhood": "Zone du Bois",
        },
        headers=auth_headers(client_token),
    ).json()

    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 7000},
        headers=auth_headers(provider_token),
    ).json()

    client.post(
        f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept",
        headers=auth_headers(client_token),
    )

    second_quote_response = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 6000},
        headers=auth_headers(provider_token),
    )
    assert second_quote_response.status_code == 400
