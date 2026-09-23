# Feature test report

**Environment:** Python 3.14.7, Django 6.1.1, `venv/`, PostgreSQL 18.6 (local `postgresql:///hospital_blood_report` for migrate/seed; test suite uses isolated DB).  
**Evidence:** `venv/bin/python manage.py test app` — **31 tests, OK** (run twice: SQLite default + PostgreSQL URL).  
**Date:** 24 Sep 2026.

Legend: **PASS** | **PASS WITH WARNING** | **FAIL** | **BLOCKED** | **N/A**

| Feature | Positive | Negative | Edge | Regression | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| W1 Home / role redirect | PASS | PASS | N/A | PASS | PASS | Anonymous 200; role redirects |
| W2 Login | PASS | PASS | PASS | PASS | PASS | Bad password, inactive user |
| W3 Registration | PASS | PASS | PASS | PASS | PASS | Admin role blocked; mismatch passwords |
| W4 Logout | PASS | N/A | N/A | PASS | PASS | |
| W5–W6 Password reset | PASS | N/A | N/A | PASS | PASS | Page loads only |
| W7 Admin dashboard | PASS | PASS | N/A | PASS | PASS | Non-admin denied |
| W8 Doctor approve/reject | PASS | PASS | N/A | PASS | PASS | URL fixed under `/dashboard/admin/` |
| W9 Patient dashboard | PASS | PASS | PASS | PASS | PASS | Search / pagination |
| W10 Book appointment | PASS | PASS | PASS | PASS | PASS | Overlap, backdate, doctor closed |
| W11 Cancel appointment | PASS | PASS | PASS | PASS | PASS | Non-pending, IDOR |
| W12–W13 Appointment detail / comments | PASS | PASS | PASS | PASS | PASS | XSS escaped in comment |
| W14 Patient profile | PASS | N/A | N/A | PASS | PASS | |
| W15 Upload report | PASS | PASS | PASS | PASS | PASS | Size/type/IDOR |
| W16–W21 Doctor flows | PASS | PASS | N/A | PASS | PASS | Status, remarks, upload |
| W22 Django admin | PASS | N/A | N/A | PASS | PASS | Staff login |
| W23 Debug admin | PASS | PASS | N/A | PASS | PASS | 403 non-staff |
| A1–A2 JWT | PASS | PASS | N/A | PASS | PASS | 401 without Bearer |
| A3 API register | PASS | PASS | N/A | PASS | PASS | No password in response |
| A4 Appointments API | PASS | PASS | PASS | PASS | PASS | Scoped queryset; patient binding |
| A5 update_status | PASS | PASS | N/A | PASS | PASS | Invalid status 400 |
| A6 Reports API | PASS | PASS | N/A | PASS | PASS | Uploader forced to caller |
| A7–A8 Admin API | PASS | PASS | N/A | PASS | PASS | User list + doctor-management PATCH |
| A9 n8n callback | PASS | PASS | PASS | PASS | PASS | Token required; 503 if unset |
| O1 healthz | PASS | N/A | N/A | PASS | PASS WITH WARNING | Runs migrate on each hit |
| O2 seed_demo_users | PASS | N/A | N/A | PASS | PASS | |
| O3 populate_demo_db | PASS | N/A | N/A | PASS | PASS | |
| O4 generate_user_tokens | PASS | N/A | N/A | PASS | PASS | |
| O5 seed_test_data | N/A | N/A | N/A | N/A | NOT APPLICABLE | Not invoked in automated suite |
| O6–O7 migrate / static | PASS | N/A | N/A | PASS | PASS | PG migrate + collectstatic |
| O8 Gunicorn 26 | PASS | N/A | N/A | PASS | PASS | Bind :8001, home 200 |
| I1 Google Drive | N/A | PASS | N/A | PASS | PASS WITH WARNING | Missing creds → RuntimeError (expected) |
| I2 n8n webhook | PASS | PASS | N/A | PASS | PASS WITH WARNING | No live n8n; timeout mocked |
| I3 Legacy webhook | PASS | N/A | N/A | PASS | PASS | Empty when unset |
| I4 IntegrationConfig | PASS | N/A | N/A | PASS | PASS | Singleton via tests |
| I5 UserToken | PASS | N/A | N/A | PASS | PASS | generate command |

**Automated test modules:** `app/tests.py`, `app/test_features.py`.
