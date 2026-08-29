from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

import app.models  # noqa: F401  (enregistre les modèles auprès de Base.metadata)
from app.api.routes import admin, auth, missions, payments, services, users
from app.core.config import get_settings
from app.core.rate_limit import limiter

settings = get_settings()

# Le schéma de base de données est géré par Alembic (voir migrations/), pas par
# l'application au démarrage : exécuter `alembic upgrade head` avant de déployer
# une nouvelle version (cf. proxiservices/README.md).
app = FastAPI(title=settings.app_name)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(services.router)
app.include_router(missions.router)
app.include_router(payments.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
