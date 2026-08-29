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
    # À vérifier/ajuster dans la documentation du compte marchand Paydunia une fois
    # celui-ci créé : url de base et chemin exacts de l'API d'initiation de paiement.
    paydunia_base_url: str = "https://api.paydunia.com"
    paydunia_webhook_url: str = ""
    paydunia_return_url: str = ""

    # Commission prélevée sur chaque transaction en séquestre (7% à 10% selon le cahier des charges)
    commission_rate: float = 0.08
    pro_subscription_price_fcfa: int = 2000
    boost_price_fcfa: int = 500

    cors_allowed_origins: list[str] = ["http://localhost:5500", "http://127.0.0.1:5500"]

    # Supabase Storage — utilisé pour l'upload sécurisé des documents KYC des
    # prestataires. supabase_service_role_key ne doit JAMAIS être exposée au frontend.
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_kyc_bucket: str = "proxiservices-kyc"


@lru_cache
def get_settings() -> Settings:
    return Settings()
