# Feature inventory

Hospital Blood Report Analyzer — modules, screens, APIs, commands, and integrations after stack migration (Sep 2026).

## Web UI

| ID | Feature | Entry | Roles |
| --- | --- | --- | --- |
| W1 | Marketing home | `/` | Public / authenticated redirect |
| W2 | Login | `/login/` | Public |
| W3 | Registration | `/register/` | Public |
| W4 | Logout | `/logout/`, `/auth/logout/` | Authenticated |
| W5 | Password reset request | `/password-reset/` | Public |
| W6 | Password reset done | `/password-reset/done/` | Public |
| W7 | Admin dashboard | `/dashboard/admin/` | Admin |
| W8 | Doctor approval / rejection | `/dashboard/admin/doctor/<id>/approve|reject/` | Admin |
| W9 | Patient dashboard | `/patient/dashboard/` | Patient |
| W10 | Book appointment (+ optional report) | `/patient/book/` | Patient |
| W11 | Cancel appointment | `/patient/appointment/<id>/cancel/` | Patient |
| W12 | Patient appointment detail | `/patient/appointment/<id>/` | Patient |
| W13 | Patient appointment comment | `/patient/appointment/<id>/comment/` | Patient |
| W14 | Patient profile edit | `/patient/profile/` | Patient |
| W15 | Standalone report upload | `/upload-report/` | Patient, Doctor |
| W16 | Doctor dashboard | `/doctor/dashboard/` | Doctor |
| W17 | Doctor appointment detail | `/doctor/appointment/<id>/` | Doctor |
| W18 | Doctor update status & remarks | `/doctor/appointment/<id>/update/` | Doctor |
| W19 | Doctor legacy status POST | `/doctor/appointment/<id>/status/` | Doctor, Admin |
| W20 | Doctor appointment comment | `/doctor/appointment/<id>/comment/` | Doctor |
| W21 | Doctor profile edit | `/doctor/profile/` | Doctor |
| W22 | Django admin | `/admin/` | Staff |
| W23 | Debug admin JSON | `/debug-admin/` | Staff |

## REST API

| ID | Feature | Method / path | Auth |
| --- | --- | --- | --- |
| A1 | JWT obtain | `POST /api/token/` | Public |
| A2 | JWT refresh | `POST /api/token/refresh/` | Refresh token |
| A3 | API register | `POST /api/register/` | Public |
| A4 | Appointments CRUD | `/api/appointments/` | JWT / session |
| A5 | Appointment status action | `POST /api/appointments/<id>/update_status/` | JWT |
| A6 | Blood reports CRUD | `/api/reports/` | JWT |
| A7 | Users CRUD | `/api/users/` | Admin |
| A8 | Doctor profiles CRUD | `/api/doctor-management/` | Admin |
| A9 | n8n health report callback | `POST /api/n8n/health-report-callback/` | Bearer callback token |

## Operations

| ID | Feature | Command / URL |
| --- | --- | --- |
| O1 | Health check | `GET /healthz/` |
| O2 | Seed demo users | `python manage.py seed_demo_users` |
| O3 | Populate demo DB | `python manage.py populate_demo_db` |
| O4 | Generate user tokens | `python manage.py generate_user_tokens` |
| O5 | Seed test data | `python manage.py seed_test_data` |
| O6 | Migrations | `python manage.py migrate` |
| O7 | Collect static | `python manage.py collectstatic` |
| O8 | Production server | Gunicorn `config.wsgi:application` |

## Integrations

| ID | Feature | Implementation |
| --- | --- | --- |
| I1 | Google Drive upload | `app/services.py` — Drive API v3 |
| I2 | n8n blood report webhook | `trigger_n8n_webhook` / async |
| I3 | Legacy post-upload webhook | `call_post_upload_api` env fallback |
| I4 | Integration config singleton | Django admin `IntegrationConfig` |
| I5 | User API token storage | `UserToken` model + admin |

## Data model (persistence)

User (roles), DoctorProfile, PatientProfile, Appointment, BloodReport, HealthReport, ReportComment, UserToken, IntegrationConfig, AuditLog, Department, Specialty.
