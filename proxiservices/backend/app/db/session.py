from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NullPool : pas de connexions persistantes entre requêtes. Nécessaire pour un
# déploiement serverless (Vercel) où chaque invocation peut tourner sur un
# nouvel event loop ; une connexion asyncpg réutilisée sur un autre event loop
# provoque des erreurs "another operation is in progress".
#
# search_path=proxiservices : les CAST de type ENUM générés par SQLAlchemy
# (ex: $1::user_role) ne sont pas qualifiés par le schéma. Sans ce réglage,
# Postgres cherche "user_role" via le search_path par défaut ("$user, public")
# et ne le trouve pas puisque le type vit dans le schema "proxiservices".
#
# statement_cache_size=0 : le pooler Supabase (PgBouncer, mode "transaction")
# peut réassigner une connexion physique différente entre deux requêtes sur la
# même connexion asyncpg, invalidant les "prepared statements" mis en cache
# côté client. Sans ce réglage : asyncpg.exceptions.InvalidSQLStatementNameError
# ("prepared statement ... does not exist"). Voir la documentation asyncpg sur
# l'utilisation avec PgBouncer.
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    poolclass=NullPool,
    connect_args={
        "server_settings": {"search_path": "proxiservices"},
        "statement_cache_size": 0,
    },
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
