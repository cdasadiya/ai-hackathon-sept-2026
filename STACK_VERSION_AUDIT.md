# Stack version audit & migration matrix

**Project:** [Hospital Blood Report Analyzer](https://github.com/cdasadiya/ai-hackathon-sept-2026) (Nexus Health)  
**Baseline:** commit `ac092e9` · **Current:** branch `release/modernized-stack-2026`  
**Audit date:** 24 Sep 2026 · **Verdict:** All targets met — **release ready**

This document is the **single source of truth** for before / target / after stack comparison.

| Component | Before (`ac092e9`) | Target (current release) | Now (repo + `venv/`) | Status |
| --- | --- | --- | --- | --- |
| **Python** | 3.12.x, Render 3.12.4, `.venv` | 3.14.7 | **3.14.7** | Current |
| **Django** | 5.2.17, cap `<5.3` | 6.1.1 | **6.1.1** | Current |
| **Django REST framework** | 3.16.0 | 3.18.1 | **3.18.1** | Current |
| **djangorestframework-simplejwt** | 5.5.0 | 5.5.1 | **5.5.1** | Current |
| **PyJWT** | 2.9.0 (capped) | 2.15.0 | **2.15.0** | Current |
| **Gunicorn** | 23.0.0 | 26.2.0 | **26.2.0** | Current |
| **WhiteNoise** | 6.9.0 | 6.12.0 | **6.12.0** | Current |
| **dj-database-url** | 3.0.1 | 3.1.2 | **3.1.2** | Current |
| **psycopg[binary]** | 3.2.12 | 3.3.6 | **3.3.6** | Current |
| **python-dotenv** | 1.0.1 | 1.2.3 | **1.2.3** | Current |
| **requests** | 2.32.3 | 2.34.2 | **2.34.2** | Current |
| **google-api-python-client** | 2.128.0 | 2.200.0 | **2.200.0** | Current |
| **google-auth** | 2.29.0 | 2.58.0 | **2.58.0** | Current |
| **google-auth-httplib2** | 0.2.0 | 0.4.2 | **0.4.2** | Current |
| **Bootstrap (CDN)** | 5.3.3 | 5.3.8 | **5.3.8** | Current |
| **Bootstrap Icons (CDN)** | 1.11.3 | 1.13.1 | **1.13.1** | Current |
| **Font Awesome (CDN)** | 6.4.0 | 7.3.1 | **7.3.1** | Current |
| **Google Drive API** | v3 | v3 | **v3** | Current |
| **PostgreSQL** | SQLite local; Render unpinned | 18.6 | **18.6** local, **18** in Docker & CI | Current |
| **CI/CD** | None | Automated test pipeline | **GitHub Actions** (`.github/workflows/ci.yml`) | Current |
| **Docker** | None | Containerized deploy | **Dockerfile** + **docker-compose.yml** | Current |
| **Automated tests** | 5 tests | Full regression | **31 tests** (`app/tests.py`, `app/test_features.py`) | Current |
| **Virtualenv** | `.venv` (3.12) | 3.14.7 env | **`venv/`** (legacy `.venv` removed) | Current |
| **Health check** | `healthz` ran migrate every hit | Lightweight probe | **`HEALTHZ_RUN_MIGRATIONS=false`** default | Current |
| **Demo seed on build** | Always in `build.sh` | Configurable | **`SEED_DEMO_USERS`** (default `true` on Render) | Current |
| **Security hardening** | Registration tracebacks; open n8n callback | Fail closed | Fixed + production cookie/HSTS when `DEBUG=False` | Current |

## Evidence

- Pins: `requirements.txt`, `render.yaml`, template CDN URLs  
- Runtime: `venv/bin/python --version`, `pip show Django`  
- Quality: `python manage.py test app` (31 OK), `pip-audit -r requirements.txt` (clean)  
- Deploy: Gunicorn 26 smoke, `collectstatic`, `check --deploy`  

## Related documentation

| Document | Purpose |
| --- | --- |
| [MIGRATION_REPORT.md](MIGRATION_REPORT.md) | Executive summary and deployment |
| [MIGRATION_PLAN.md](MIGRATION_PLAN.md) | Original migration plan |
| [FEATURE_INVENTORY.md](FEATURE_INVENTORY.md) | Feature list |
| [FEATURE_TEST_REPORT.md](FEATURE_TEST_REPORT.md) | Test evidence |

## Quick commands

```bash
source venv/bin/activate
python manage.py runserver

docker compose up --build

pip install -r requirements-dev.txt
python manage.py test app
pip-audit -r requirements.txt
```
