# Stack version audit (post-migration)

**Status date:** 24 Sep 2026  
**Repository:** Hospital Blood Report Analyzer  
**Verdict:** All audited components at **Current release** targets. **Product ready.**

| Component | Before | Current release (target) | Installed / declared now | Status |
| --- | --- | --- | --- | --- |
| Python | 3.12.14 / Render 3.12.4 | 3.14.7 | **3.14.7** (`venv/`) | Current |
| Django | 5.2.17 (`<5.3`) | 6.1.1 | **6.1.1** | Current |
| Django REST framework | 3.16.0 | 3.18.1 | **3.18.1** | Current |
| simplejwt | 5.5.0 | 5.5.1 | **5.5.1** | Current |
| PyJWT | 2.9.0 | 2.15.0 | **2.15.0** | Current |
| Gunicorn | 23.0.0 | 26.2.0 | **26.2.0** | Current |
| WhiteNoise | 6.9.0 | 6.12.0 | **6.12.0** | Current |
| dj-database-url | 3.0.1 | 3.1.2 | **3.1.2** | Current |
| psycopg | 3.2.12 | 3.3.6 | **3.3.6** | Current |
| python-dotenv | 1.0.1 | 1.2.3 | **1.2.3** | Current |
| requests | 2.32.3 | 2.34.2 | **2.34.2** | Current |
| google-api-python-client | 2.128.0 | 2.200.0 | **2.200.0** | Current |
| google-auth | 2.29.0 | 2.58.0 | **2.58.0** | Current |
| google-auth-httplib2 | 0.2.0 | 0.4.2 | **0.4.2** | Current |
| Bootstrap | 5.3.3 | 5.3.8 | **5.3.8** (CDN) | Current |
| Bootstrap Icons | 1.11.3 | 1.13.1 | **1.13.1** (CDN) | Current |
| Font Awesome | 6.4.0 | 7.3.1 | **7.3.1** (CDN) | Current |
| Google Drive API | v3 | v3 | **v3** | Current |
| PostgreSQL | unpinned | 18.6 | **18.6** local / **18** in Docker & CI | Current |

**Evidence:** `requirements.txt`, template CDN URLs, `render.yaml`, `docker-compose.yml`, `pip show` / `venv/bin/python --version`, local `psql` version, **31 passing tests**, `pip-audit` clean.

**Interactive canvas:** [stack-version-audit.canvas.tsx](/home/shreeji/.cursor/projects/home-shreeji-ai-hackathon-sept-2026/canvases/stack-version-audit.canvas.tsx)
