# Migration plan

Target stack is the **Current release** column of the Stack Version Audit (23 Sep 2026). Where that column names two acceptable lines, the newer feature release is the target and the reason is recorded below.

## Current architecture

Django monolith. `config` holds settings, URLs, and WSGI. `app` holds users, appointments, blood reports, the REST API, and the server-rendered UI. Templates load Bootstrap, Bootstrap Icons, and Font Awesome from CDNs. There is no Node build and no Docker or CI config.

Persistence is SQLite when `DATABASE_URL` is unset, and PostgreSQL when it is set. Render starts Gunicorn, runs migrations, and expects Postgres. Google Drive and n8n are optional integrations configured in the `IntegrationConfig` singleton.

## Version decisions

| Component | Installed before | Target | Decision |
| --- | --- | --- | --- |
| Python | 3.12.14 local, 3.12.4 on Render | 3.14.7 | Install 3.14.7 with pyenv. The OS package is only 3.14.4, which is not the audit target. |
| Django | 5.2.17 (`>=5.1,<5.3`) | 6.1.1 | The audit lists 6.1.1 as the feature release and 5.2.17 as LTS. 6.1.1 is the current release. 5.2 stays supported, but staying there would ignore the newer target. |
| PostgreSQL | unpinned; local server is already 18.6 | 18.6 | Use the local 18.6 server. Render's managed database version cannot be pinned to 18.6 from this repo. |
| Django REST framework | 3.16.0 | 3.18.1 | Direct pin. |
| simplejwt | 5.5.0 | 5.5.1 | Direct pin. 5.5.1 removes the `PyJWT<2.10` cap. |
| PyJWT | 2.9.0 transitive | 2.15.0 | Pin explicitly. |
| Gunicorn | 23.0.0 | 26.2.0 | Direct pin. Start command flags stay the same if Gunicorn 26 still accepts them. |
| WhiteNoise | 6.9.0 | 6.12.0 | Direct pin. |
| dj-database-url | 3.0.1 | 3.1.2 | Direct pin. |
| psycopg | 3.2.12 | 3.3.6 | Direct pin, with the binary extra. |
| python-dotenv | 1.0.1 | 1.2.3 | Direct pin. `load_dotenv` call stays. |
| requests | 2.32.3 | 2.34.2 | Direct pin. |
| google-api-python-client | 2.128.0 | 2.200.0 | Direct pin. Drive API remains v3. |
| google-auth | 2.29.0 | 2.58.0 | Direct pin. |
| google-auth-httplib2 | 0.2.0 | 0.4.2 | Direct pin. |
| Bootstrap | 5.3.3 | 5.3.8 | CDN only. No Bootstrap 6 exists. |
| Bootstrap Icons | 1.11.3 | 1.13.1 | CDN only. Class names are unchanged. |
| Font Awesome | 6.4.0 | 7.3.1 | CDN only. Icon classes on the homepage are checked against the 7.3.1 stylesheet. |

## Breaking changes that affect this code

Django 6.0 removes positional `Model.save()` arguments, the `FORMS_URLFIELD_ASSUME_HTTPS` setting, and `CheckConstraint(check=...)`. This repository does not use those removed forms. `Model.save()` overrides keep keyword arguments only when calling `super()`.

Django 6.0 changes `forms.URLField` to assume `https`. Stored `URLField` values are full URLs already.

Django 6.1 removes the `login()` fallback that used `request.user` when `user` is omitted. This app always passes the user.

No application code uses the removed admin `log_deletion()` API, `django.utils.itercompat`, or Oracle.

## Code changes required by the migration

- Pin `requirements.txt` to the target releases, including PyJWT.
- Recreate the virtual environment with Python 3.14.7.
- Point local `DATABASE_URL` at PostgreSQL 18.6 and load the existing SQLite data into it. Do not delete `db.sqlite3`.
- Set Render `PYTHON_VERSION` to 3.14.7.
- Update CDN links.
- Stop the registration view from returning a Python traceback to the browser.
- Require the n8n callback token. An empty token currently accepts any caller.
- Make appointment API creates run `full_clean()` and bind the patient to the authenticated patient. The model already documents this rule; the API only checked that the start time was in the future.
- Force blood-report API creates to record the authenticated user as uploader.

## Database

Existing migrations stay. No new schema is required for the version bump. Fresh install is `migrate`. Existing SQLite rows are dumped and loaded into PostgreSQL 18.6. The SQLite file is left in place.

## Testing strategy

Django `TestCase` against PostgreSQL covers each feature's success path, invalid input, and authorization. External Google Drive and n8n calls are not given live credentials; webhook helpers are tested with an unset URL and with a mocked HTTP failure.

## Deployment

`build.sh`, the Procfile, and `render.yaml` keep the same command shape. Gunicorn becomes 26.2.0. Render must provide Python 3.14.7. Render still chooses the managed Postgres major.

## Security notes carried into the work

- Do not print the demo seed password in new docs.
- Do not copy the committed Drive folder id into new docs.
- Registration tracebacks and the open n8n callback are fixed.
- Demo user seeding in `build.sh` stays, because removing it would delete the deployed demo accounts. It remains a production warning.

## Rollback

Restore `requirements.txt` and the CDN links from commit `ac092e9`, recreate the Python 3.12 virtualenv, and point `DATABASE_URL` back at SQLite or the previous Render database. Application migrations are not rewritten, so schema rollback is not required for the version bump.

## Risks

- simplejwt 5.5.1 does not declare an upper Django bound. Runtime tests decide whether Django 6.1.1 is actually compatible.
- Font Awesome 7 may rename an icon used on the homepage.
- Render may not publish the 3.14.7 runtime image on the day of deploy.
- Render Postgres may not be 18.
