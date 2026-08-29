from tests.conftest import auth_headers, login, register_user


def test_client_sees_all_own_missions_regardless_of_status(client):
    register_user(client, email="client@example.com", password="clientpass1", role="client")
    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    client_token = login(client, email="client@example.com", password="clientpass1")
    provider_token = login(client, email="provider@example.com", password="providerpass1")
    admin_token = login(client, email="admin@example.com", password="adminpass1")

    category_id = client.post(
        "/api/services/categories",
        json={"name": "Informatique", "slug": "informatique"},
        headers=auth_headers(admin_token),
    ).json()["id"]

    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Réparation ordinateur portable",
            "description": "L'écran ne s'allume plus depuis hier soir",
            "budget_fcfa": 20000,
            "neighborhood": "Dassasgho",
        },
        headers=auth_headers(client_token),
    ).json()

    # Tant que la mission n'est qu'au statut "open", /api/missions/mine la retourne déjà
    mine_before = client.get("/api/missions/mine", headers=auth_headers(client_token)).json()
    assert len(mine_before) == 1

    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 18000},
        headers=auth_headers(provider_token),
    ).json()
    client.post(
        f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept",
        headers=auth_headers(client_token),
    )

    # Une fois acceptée (donc plus "open"), la mission reste visible via /mine
    # alors qu'elle a disparu de la liste publique des missions ouvertes.
    mine_after = client.get("/api/missions/mine", headers=auth_headers(client_token)).json()
    assert len(mine_after) == 1
    assert mine_after[0]["status"] == "accepted"

    open_missions = client.get("/api/missions").json()
    assert open_missions == []


def test_provider_mine_only_shows_missions_they_are_assigned_to(client):
    register_user(client, email="client2@example.com", password="clientpass1", role="client")
    register_user(client, email="provider2@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin2@example.com", password="adminpass1", role="admin")
    client_token = login(client, email="client2@example.com", password="clientpass1")
    provider_token = login(client, email="provider2@example.com", password="providerpass1")
    admin_token = login(client, email="admin2@example.com", password="adminpass1")

    category_id = client.post(
        "/api/services/categories",
        json={"name": "Cours particuliers", "slug": "cours"},
        headers=auth_headers(admin_token),
    ).json()["id"]

    # Aucune mission acceptée pour ce prestataire pour l'instant.
    assert client.get("/api/missions/mine", headers=auth_headers(provider_token)).json() == []

    mission = client.post(
        "/api/missions",
        json={
            "category_id": category_id,
            "title": "Cours de mathématiques niveau terminale",
            "description": "Préparation aux examens de fin d'année",
            "budget_fcfa": 6000,
            "neighborhood": "Karpala",
        },
        headers=auth_headers(client_token),
    ).json()
    quote = client.post(
        f"/api/missions/{mission['id']}/quotes",
        json={"amount_fcfa": 5500},
        headers=auth_headers(provider_token),
    ).json()
    client.post(
        f"/api/missions/{mission['id']}/quotes/{quote['id']}/accept",
        headers=auth_headers(client_token),
    )

    mine = client.get("/api/missions/mine", headers=auth_headers(provider_token)).json()
    assert len(mine) == 1
    assert mine[0]["id"] == mission["id"]
