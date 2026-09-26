"""Repair hackathon demo / showcase logins on the running web process.

Render can boot gunicorn without running scripts/render_start.sh, and
SEED_DEMO_USERS is sometimes false on the service even when render.yaml
says true. Login then fails because admin1/doctor1/patient1 were never
inserted. Showcase rows can also be missing after a fresh Postgres attach.
This runs once per process (login, JWT, healthz) so those accounts exist
before Django checks the password.
"""

import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)

_done = False
_lock = threading.Lock()

_DEMO_PASSWORD = "Pass1234!"
_SHOWCASE_PASSWORD = "Showcase123!"


def _showcase_enabled():
    return os.environ.get("SEED_SHOWCASE", "true").strip().lower() in {
        "1",
        "true",
        "t",
        "yes",
        "y",
        "on",
    }


def ensure_demo_accounts():
    global _done
    if _done:
        return
    if any(flag in sys.argv for flag in ("test", "migrate", "makemigrations", "collectstatic")):
        return
    with _lock:
        if _done:
            return
        try:
            from django.contrib.auth import get_user_model
            from django.core.management import call_command

            User = get_user_model()
            admin = User.objects.filter(username="admin1").first()
            patient = User.objects.filter(username="patient1").first()
            doctor = User.objects.filter(username="doctor1").first()
            demos_ok = bool(
                admin
                and admin.is_active
                and admin.is_staff
                and admin.check_password(_DEMO_PASSWORD)
                and patient
                and patient.is_active
                and (not patient.is_staff)
                and patient.check_password(_DEMO_PASSWORD)
                and doctor
                and doctor.is_active
                and (not doctor.is_staff)
                and doctor.check_password(_DEMO_PASSWORD)
            )
            if not demos_ok:
                call_command("seed_demo_users")

            if _showcase_enabled():
                showcase = User.objects.filter(username="case_patient_01").first()
                showcase_ok = bool(
                    showcase
                    and showcase.is_active
                    and showcase.check_password(_SHOWCASE_PASSWORD)
                )
                if not showcase_ok:
                    call_command("seed_showcase")

            # Only mark complete when the critical demo roster authenticates.
            admin = User.objects.filter(username="admin1").first()
            patient = User.objects.filter(username="patient1").first()
            doctor = User.objects.filter(username="doctor1").first()
            if not (
                admin
                and admin.is_active
                and admin.is_staff
                and admin.check_password(_DEMO_PASSWORD)
                and patient
                and patient.is_active
                and (not patient.is_staff)
                and patient.check_password(_DEMO_PASSWORD)
                and doctor
                and doctor.is_active
                and (not doctor.is_staff)
                and doctor.check_password(_DEMO_PASSWORD)
            ):
                logger.error("Demo account repair finished but roster still cannot authenticate")
                return

            _done = True
        except Exception:
            logger.exception("Demo account repair failed")
