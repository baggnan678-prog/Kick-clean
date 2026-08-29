from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NullPool : pas de connexions persistantes entre requêtes. Nécessaire pour un
# déploiement serverless (Vercel) où chaque invocation peut tourner sur un
# nouvel event loop ; une connexion asyncpg réutilisée sur un autre event loop
# provoque des erreurs "another operation is in progress".
engine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",
    poolclass=NullPool,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
