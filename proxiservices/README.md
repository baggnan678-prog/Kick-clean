# ProxiServices — Ébauche de plateforme (MVP scaffold)

Ce dossier contient une **ébauche technique** de la plateforme ProxiServices décrite
dans le cahier des charges : une marketplace mettant en relation particuliers et
prestataires indépendants pour des services de proximité (plomberie, électricité,
informatique, cours particuliers, ménage...).

**Important** : il s'agit d'un squelette de projet fonctionnel (backend + frontend
qui communiquent réellement), pas d'un produit fini prêt pour la production. Voir
la section « Ce qu'il reste à faire » avant tout déploiement réel.

Ce dossier est indépendant du reste du dépôt (le site vitrine Kick Clean à la racine) :
aucun fichier existant n'a été modifié.

## Architecture

```
proxiservices/
├── backend/         API FastAPI (Python), SQLAlchemy async, PostgreSQL
│   └── app/
│       ├── core/    configuration, sécurité (Argon2, JWT), rate limiting
│       ├── db/      connexion base de données
│       ├── models/  tables SQLAlchemy (users, missions, quotes, transactions, ...)
│       ├── schemas/ validation Pydantic des entrées/sorties
│       └── api/     routes REST
└── frontend/        Pages statiques HTML/CSS/JS (aucun framework, aucune dépendance)
```

## Correspondance avec le cahier des charges

| Section du cahier des charges | Implémentation |
| --- | --- |
| Stack à coût minimal | FastAPI + PostgreSQL async (`asyncpg`), compatible Supabase/Neon/Render/Fly.io |
| Mots de passe hachés (Argon2/Bcrypt) | `app/core/security.py` — Argon2 via `argon2-cffi` |
| JWT à expiration courte | `app/core/security.py` — access token courte durée + refresh token |
| Validation stricte des entrées (Pydantic) | `app/schemas/*.py` — contraintes de longueur, bornes numériques, formats |
| Rate limiting (force brute) | `slowapi` sur `/api/auth/login` (5 requêtes/minute par IP) |
| Séquestre des fonds (escrow) | `app/models/transaction.py` + logique dans `api/routes/missions.py` (les fonds ne sont libérés qu'après validation du client) |
| Validation cryptographique des webhooks Paydunia | `api/routes/payments.py` — vérification HMAC-SHA256 en comparaison à temps constant |
| Journalisation des actions sensibles | `app/models/audit_log.py`, alimenté à chaque connexion, acceptation de devis, clôture de mission |
| Commission 7-10% | `commission_rate` dans la configuration, appliqué à l'acceptation d'un devis |
| Abonnement Pro / Boost | `app/models/subscription.py`, `app/models/boost.py` (modèles de données prêts ; la logique de paiement associée reste à brancher) |
| Espaces Client / Prestataire / Admin | Routes `/api/missions`, `/api/services`, `/api/admin` + pages `frontend/espace-client.html`, `frontend/espace-prestataire.html` |

## Base de données : projet Supabase dédié

La base de données de production vit dans le projet Supabase **« sey »**
(organisation « Seydou »), dans un **schema PostgreSQL dédié `proxiservices`**,
isolé des tables `public.*` de l'application existante hébergée dans ce même
projet. Aucune table de ProxiServices n'est dans `public.*`, et RLS est activé
sur toutes les tables ProxiServices par défaut.

Pour connecter le backend à cette base, récupérez la chaîne de connexion dans
le dashboard Supabase (Project Settings → Database → Connection string, mode
"Transaction pooler" recommandé) et adaptez-la au format attendu :

```
postgresql+asyncpg://postgres:<mot-de-passe>@<host>:5432/postgres
```

## Migrations de base de données (Alembic)

Le schéma est versionné avec Alembic (dossier `migrations/`), pas créé
automatiquement au démarrage de l'application. Après avoir configuré
`DATABASE_URL` :

```bash
cd proxiservices/backend
alembic upgrade head      # applique les migrations manquantes
alembic revision -m "..."  # crée une nouvelle migration après avoir modifié un modèle
```

La migration initiale (`migrations/versions/0001_initial_schema.py`) a été
testée de bout en bout (upgrade / downgrade / re-upgrade) sur un PostgreSQL 16
local avant d'être appliquée au projet Supabase réel. Sur la base Supabase
« sey », l'historique Alembic a été synchronisé (`alembic_version` positionné
sur `0001_initial_schema`) sans rejouer le SQL, puisque le schéma y avait déjà
été créé directement.

## Lancer le backend en local

```bash
cd proxiservices/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner de vraies valeurs (JWT_SECRET_KEY, DATABASE_URL...)
alembic upgrade head
uvicorn app.main:app --reload
```

L'API est alors disponible sur `http://localhost:8000` (documentation interactive
sur `http://localhost:8000/docs`).

## Lancer les tests

La suite pytest tourne contre un vrai PostgreSQL (pas de sqlite : le schéma
dédié et les types ENUM sont spécifiques à Postgres). En local :

```bash
cd proxiservices/backend
pip install -r requirements-dev.txt
# Un PostgreSQL local est nécessaire, par exemple :
#   sudo service postgresql start
#   sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'test';"
#   sudo -u postgres psql -c "CREATE DATABASE proxiservices_test;"
pytest -v
```

16 tests couvrent : inscription/connexion, rejet de mauvais mot de passe,
rafraîchissement de jeton, limitation de débit sur la connexion, le cycle
complet mission → devis → acceptation (séquestre) → clôture, les contrôles de
rôle (client/prestataire/admin), et la vérification de signature du webhook
Paydunia (signature manquante, invalide, référence inconnue).

## Lancer le frontend en local

Le frontend est 100% statique (aucun build nécessaire). Servez le dossier avec
n'importe quel serveur statique, par exemple :

```bash
cd proxiservices/frontend
python3 -m http.server 5500
```

Puis ouvrez `http://localhost:5500`. Par défaut, les pages appellent l'API sur
`http://localhost:8000` ; pour pointer vers une autre URL (ex: API déployée sur
Render/Fly.io), exécutez dans la console du navigateur :

```js
localStorage.setItem("ps_api_base_url", "https://votre-api.example.com");
```

## Déploiement suggéré (coût minimal, cf. cahier des charges)

- **Frontend** : Vercel, Netlify ou GitHub Pages (dossier `frontend/`).
- **Backend** : Render ou Fly.io (offres gratuites), ou un VPS mutualisé d'entrée
  de gamme si la charge augmente.
- **Base de données** : Supabase ou Neon (PostgreSQL managé, quota gratuit).
- **Paiement** : Paydunia — configurer `PAYDUNIA_API_KEY` et
  `PAYDUNIA_WEBHOOK_SECRET` dans les variables d'environnement du backend déployé.

## Ce qu'il reste à faire avant une mise en production

Cette ébauche pose les fondations techniques et de sécurité décrites dans le
cahier des charges, mais plusieurs points restent volontairement hors périmètre
d'un MVP scaffold :

- **Intégration réelle de l'API Paydunia** : l'initiation de paiement (obtention
  d'une URL de paiement) n'est pas implémentée — seule la réception sécurisée du
  webhook de confirmation l'est.
- **Gestion des litiges** : le statut `disputed` existe dans le modèle de données,
  mais le flux de médiation (côté admin) reste à construire.
- **Vérification d'identité des prestataires (KYC)**, upload de photos de profil,
  géolocalisation avancée (recherche par rayon), notifications (SMS/e-mail),
  interface d'administration complète (modération, gestion des abonnements/boosts).
- **Sécurité en production** : configurer HTTPS (Let's Encrypt) au niveau de
  l'hébergeur, définir des secrets forts et uniques, restreindre `CORS_ALLOWED_ORIGINS`
  au(x) domaine(s) réel(s) du frontend.
