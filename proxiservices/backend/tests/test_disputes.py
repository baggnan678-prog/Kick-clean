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
        json={"name": "Ménage", "slug": "menage"},
        headers=auth_headers(admin_token),
    ).json()["id"]

    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Grand ménage de printemps",
            "description": "Nettoyage complet de l'appartement avant déménagement",
            "budget_fcfa": 10000,
            "neighborhood": "Gounghin",
        },
        headers=auth_headers(client_token),
    ).json()

    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 9000},
        headers=auth_headers(provider_token),
    ).json()

    client.post(
        f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept",
        headers=auth_headers(client_token),
    )

    return mission, client_token, provider_token, admin_token


def test_client_can_open_dispute(client):
    mission, client_token, _, _ = _setup_accepted_mission(client)

    response = client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Le travail n'a pas été terminé correctement"},
        headers=auth_headers(client_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disputed"
    assert response.json()["dispute_reason"] == "Le travail n'a pas été terminé correctement"


def test_provider_can_open_dispute(client):
    mission, _, provider_token, _ = _setup_accepted_mission(client)

    response = client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Le client refuse de valider sans raison"},
        headers=auth_headers(provider_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disputed"


def test_unrelated_user_cannot_open_dispute(client):
    mission, _, _, _ = _setup_accepted_mission(client)
    register_user(client, email="outsider@example.com", password="outsiderpass1", role="client")
    outsider_token = login(client, email="outsider@example.com", password="outsiderpass1")

    response = client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Je n'ai rien à voir avec cette mission"},
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403


def test_admin_resolve_dispute_release_to_provider(client):
    mission, client_token, _, admin_token = _setup_accepted_mission(client)
    client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Litige sur la qualité du travail"},
        headers=auth_headers(client_token),
    )

    response = client.post(
        f"/api/admin/disputes/{mission['id']}/resolve",
        json={"resolution": "release", "admin_note": "Travail vérifié, conforme"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    disputes = client.get("/api/admin/disputes", headers=auth_headers(admin_token)).json()
    assert disputes == []


def test_admin_resolve_dispute_refund_to_client(client):
    mission, client_token, _, admin_token = _setup_accepted_mission(client)
    client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Prestation jamais réalisée"},
        headers=auth_headers(client_token),
    )

    response = client.post(
        f"/api/admin/disputes/{mission['id']}/resolve",
        json={"resolution": "refund"},
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_non_admin_cannot_resolve_dispute(client):
    mission, client_token, _, _ = _setup_accepted_mission(client)
    client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Litige quelconque"},
        headers=auth_headers(client_token),
    )

    response = client.post(
        f"/api/admin/disputes/{mission['id']}/resolve",
        json={"resolution": "release"},
        headers=auth_headers(client_token),
    )
    assert response.status_code == 403


def test_cannot_dispute_open_mission(client):
    register_user(client, email="client2@example.com", password="clientpass1", role="client")
    register_user(client, email="admin2@example.com", password="adminpass1", role="admin")
    client_token = login(client, email="client2@example.com", password="clientpass1")
    admin_token = login(client, email="admin2@example.com", password="adminpass1")

    category_id = client.post(
        "/api/services/categories",
        json={"name": "Jardinage", "slug": "jardinage"},
        headers=auth_headers(admin_token),
    ).json()["id"]

    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Taille de haie",
            "description": "Taille de haie dans le jardin avant la saison des pluies",
            "budget_fcfa": 5000,
            "neighborhood": "Tampouy",
        },
        headers=auth_headers(client_token),
    ).json()

    response = client.post(
        f"/api/missions/{mission['id']}/dispute",
        json={"reason": "Litige prématuré"},
        headers=auth_headers(client_token),
    )
    assert response.status_code == 400
