from tests.conftest import auth_headers, login, register_user


def test_non_admin_blocked_from_admin_stats(client):
    register_user(client, email="client@example.com", password="clientpass1", role="client")
    token = login(client, email="client@example.com", password="clientpass1")

    response = client.get("/api/admin/stats", headers=auth_headers(token))
    assert response.status_code == 403


def test_admin_can_read_empty_stats(client):
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    token = login(client, email="admin@example.com", password="adminpass1")

    response = client.get("/api/admin/stats", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json() == {"commission_totale_fcfa": 0, "missions_totales": 0}


def test_admin_disputes_list_empty_by_default(client):
    register_user(client, email="admin2@example.com", password="adminpass1", role="admin")
    token = login(client, email="admin2@example.com", password="adminpass1")

    response = client.get("/api/admin/disputes", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json() == []
