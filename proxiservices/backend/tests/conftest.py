import asyncio
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:test@127.0.0.1:5432/proxiservices_test",
)
os.environ.setdefault("PAYDUNIA_WEBHOOK_SECRET", "test-webhook-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import app.models  # noqa: F401  (enregistre les modèles auprès de Base.metadata)
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import engine
from app.main import app as fastapi_app


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Crée le schéma une fois pour toute la session de tests, le supprime à la fin."""

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{Base.metadata.schema}"'))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _drop() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_drop())


@pytest.fixture()
def client():
    """Un client de test avec une base vidée et un limiteur de débit réinitialisé."""

    async def _truncate() -> None:
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())

    asyncio.run(_truncate())
    limiter.reset()

    with TestClient(fastapi_app) as test_client:
        yield test_client


def register_user(client: TestClient, *, email: str, password: str, role: str, full_name: str = "Test User") -> dict:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "full_name": full_name, "password": password, "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, *, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
