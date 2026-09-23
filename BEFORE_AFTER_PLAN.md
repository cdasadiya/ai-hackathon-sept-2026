# Before and after plan (final)

## Before (baseline commit `ac092e9`)

| Layer | Version / state |
| --- | --- |
| Python | 3.12.x (`.venv`), Render **3.12.4** |
| Django | **5.2.17** allowed, pinned `<5.3` |
| DRF / JWT / Gunicorn / Google / requests / dotenv | 2023–2024 pins (see audit) |
| PostgreSQL | SQLite locally; Render Postgres unpinned |
| Frontend CDN | Bootstrap **5.3.3**, Icons **1.11.3**, Font Awesome **6.4.0** |
| CI/CD | None |
| Docker | None |
| Automated tests | **5** tests (`app/tests.py`) |
| Production hygiene | `healthz` ran migrate every request; demo seed always in build |

## After (migration complete)

| Layer | Version / state |
| --- | --- |
| Python | **3.14.7** (`venv/`) |
| Django | **6.1.1** |
| DRF | **3.18.1** |
| simplejwt / PyJWT | **5.5.1** / **2.15.0** |
| Gunicorn / WhiteNoise | **26.2.0** / **6.12.0** |
| DB drivers / config | psycopg **3.3.6**, dj-database-url **3.1.2**, dotenv **1.2.3** |
| HTTP / Google | requests **2.34.2**, google-api-python-client **2.200.0**, google-auth **2.58.0**, httplib2 transport **0.4.2** |
| PostgreSQL | **18.6** local; CI uses **postgres:18** |
| Frontend CDN | Bootstrap **5.3.8**, Icons **1.13.1**, Font Awesome **7.3.1** |
| CI/CD | **GitHub Actions** — tests, deploy check, ruff (F), pip-audit |
| Docker | **Dockerfile** + **docker-compose.yml** (Postgres 18 + Gunicorn web) |
| Automated tests | **31** tests (`app/tests.py` + `app/test_features.py`) |
| Docs | `MIGRATION_*`, `FEATURE_*`, `STACK_VERSION_AUDIT.md`, `.env.example` |
| Render | `PYTHON_VERSION=3.14.7`, `HEALTHZ_RUN_MIGRATIONS=false`, optional `SEED_DEMO_USERS` |
| Legacy `.venv` | Removed; use **`venv/`** only |

## Execution phases (completed)

1. Audit → target matrix → `MIGRATION_PLAN.md`
2. Dependency pin + `venv` on Python 3.14.7
3. Django 6 code + template CDN updates
4. Security fixes (registration, n8n callback, API scoping)
5. PostgreSQL migrate/seed + full test suite
6. Production hardening (healthz, build seed flag, SSL cookies)
7. Docker + CI/CD + dev tooling (`requirements-dev.txt`, `ruff.toml`)
8. Documentation + stack audit refresh
9. Git commit and push to `origin/main`

## Operational commands

```bash
# Local dev
source venv/bin/activate
python manage.py runserver

# Docker (production-like)
docker compose up --build

# CI locally
pip install -r requirements-dev.txt
python manage.py test app
ruff check app/test_features.py app/tests.py manage.py config/wsgi.py --select F
pip-audit -r requirements.txt
```
