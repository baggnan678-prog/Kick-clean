from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiteur de requêtes par IP — utilisé notamment sur /api/auth/login pour
# contrer les attaques par force brute (cf. exigences de sécurité).
limiter = Limiter(key_func=get_remote_address)
