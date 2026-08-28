from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration centralisée, chargée depuis les variables d'environnement / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ProxiServices API"
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/proxiservices"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    paydunia_api_key: str = ""
    paydunia_webhook_secret: str = "change-me"

    # Commission prélevée sur chaque transaction en séquestre (7% à 10% selon le cahier des charges)
    commission_rate: float = 0.08
    pro_subscription_price_fcfa: int = 2000
    boost_price_fcfa: int = 500

    cors_allowed_origins: list[str] = ["http://localhost:5500", "http://127.0.0.1:5500"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
