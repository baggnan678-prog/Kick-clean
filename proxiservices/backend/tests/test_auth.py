from tests.conftest import auth_headers, login, register_user


def test_register_and_login(client):
    register_user(client, email="client@example.com", password="supersecret1", role="client")
    token = login(client, email="client@example.com", password="supersecret1")
    assert token

    response = client.get("/api/users/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["email"] == "client@example.com"
    assert response.json()["role"] == "client"


def test_duplicate_email_rejected(client):
    register_user(client, email="dup@example.com", password="supersecret1", role="client")
    response = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "full_name": "Autre", "password": "supersecret2", "role": "client"},
    )
    assert response.status_code == 409


def test_wrong_password_rejected(client):
    register_user(client, email="wrongpass@example.com", password="supersecret1", role="client")
    response = client.post(
        "/api/auth/login", json={"email": "wrongpass@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401


def test_refresh_token_issues_new_access_token(client):
    register_user(client, email="refresh@example.com", password="supersecret1", role="client")
    login_response = client.post(
        "/api/auth/login", json={"email": "refresh@example.com", "password": "supersecret1"}
    )
    refresh_token = login_response.json()["refresh_token"]

    response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_unauthenticated_me_rejected(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_login_rate_limited_after_five_attempts(client):
    register_user(client, email="ratelimit@example.com", password="supersecret1", role="client")
    statuses = [
        client.post(
            "/api/auth/login", json={"email": "ratelimit@example.com", "password": "wrongpassword"}
        ).status_code
        for _ in range(7)
    ]
    assert statuses.count(401) == 5
    assert statuses.count(429) == 2
