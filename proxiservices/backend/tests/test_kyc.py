import io

from tests.conftest import auth_headers, login, register_user


async def _fake_upload_kyc_document(*, path: str, content: bytes, content_type: str) -> str:
    return path


async def _fake_create_signed_url(*, path: str, expires_in_seconds: int = 120) -> str:
    return f"https://storage.example.com/signed/{path}?expires_in={expires_in_seconds}"


def _pdf_file():
    return {"file": ("piece_identite.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")}


def test_provider_can_submit_kyc_document(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.users.upload_kyc_document", _fake_upload_kyc_document)

    register_user(client, email="provider@example.com", password="providerpass1", role="provider")
    token = login(client, email="provider@example.com", password="providerpass1")

    response = client.post(
        "/api/users/me/kyc-document", files=_pdf_file(), headers=auth_headers(token)
    )
    assert response.status_code == 202, response.text
    assert response.json()["kyc_status"] == "pending"


def test_client_cannot_submit_kyc_document(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.users.upload_kyc_document", _fake_upload_kyc_document)

    register_user(client, email="client@example.com", password="clientpass1", role="client")
    token = login(client, email="client@example.com", password="clientpass1")

    response = client.post(
        "/api/users/me/kyc-document", files=_pdf_file(), headers=auth_headers(token)
    )
    assert response.status_code == 403


def test_kyc_document_rejects_bad_content_type(client):
    register_user(client, email="provider2@example.com", password="providerpass1", role="provider")
    token = login(client, email="provider2@example.com", password="providerpass1")

    response = client.post(
        "/api/users/me/kyc-document",
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/x-msdownload")},
        headers=auth_headers(token),
    )
    assert response.status_code == 400


def test_admin_kyc_approval_flow(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.users.upload_kyc_document", _fake_upload_kyc_document)
    monkeypatch.setattr("app.api.routes.admin.create_signed_url", _fake_create_signed_url)

    provider = register_user(client, email="provider3@example.com", password="providerpass1", role="provider")
    provider_token = login(client, email="provider3@example.com", password="providerpass1")
    register_user(client, email="admin@example.com", password="adminpass1", role="admin")
    admin_token = login(client, email="admin@example.com", password="adminpass1")

    client.post("/api/users/me/kyc-document", files=_pdf_file(), headers=auth_headers(provider_token))

    pending = client.get("/api/admin/kyc/pending", headers=auth_headers(admin_token)).json()
    assert len(pending) == 1
    assert pending[0]["id"] == provider["id"]

    document_url = client.get(
        f"/api/admin/kyc/{provider['id']}/document-url", headers=auth_headers(admin_token)
    )
    assert document_url.status_code == 200
    assert "signed" in document_url.json()["url"]

    approve_response = client.post(
        f"/api/admin/kyc/{provider['id']}/approve", headers=auth_headers(admin_token)
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["kyc_status"] == "approved"
    assert approve_response.json()["is_verified_provider"] is True


def test_admin_kyc_rejection_requires_reason(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.users.upload_kyc_document", _fake_upload_kyc_document)

    provider = register_user(client, email="provider4@example.com", password="providerpass1", role="provider")
    provider_token = login(client, email="provider4@example.com", password="providerpass1")
    register_user(client, email="admin2@example.com", password="adminpass1", role="admin")
    admin_token = login(client, email="admin2@example.com", password="adminpass1")

    client.post("/api/users/me/kyc-document", files=_pdf_file(), headers=auth_headers(provider_token))

    missing_reason = client.post(f"/api/admin/kyc/{provider['id']}/reject", json={}, headers=auth_headers(admin_token))
    assert missing_reason.status_code == 422

    reject_response = client.post(
        f"/api/admin/kyc/{provider['id']}/reject",
        json={"reason": "Document illisible"},
        headers=auth_headers(admin_token),
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["kyc_status"] == "rejected"


def test_document_url_404_when_no_document(client):
    provider = register_user(client, email="provider5@example.com", password="providerpass1", role="provider")
    register_user(client, email="admin3@example.com", password="adminpass1", role="admin")
    admin_token = login(client, email="admin3@example.com", password="adminpass1")

    response = client.get(f"/api/admin/kyc/{provider['id']}/document-url", headers=auth_headers(admin_token))
    assert response.status_code == 404
