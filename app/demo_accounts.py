"""Repair hackathon demo logins on the running web process.

Render can boot gunicorn without running scripts/render_start.sh, and
SEED_DEMO_USERS is sometimes false on the service even when render.yaml
says true. Login then fails because admin1/doctor1/patient1 were never
inserted. This runs once per process, including on the login request, so
those accounts exist before Django checks the password.
"""

import logging
import os
import sys
import threading

logger = logging.getLogger(__name__)

_done = False
_lock = threading.Lock()


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
            if (
                admin
                and admin.is_active
                and admin.check_password("Pass1234!")
                and patient
                and patient.is_active
                and patient.check_password("Pass1234!")
                and doctor
                and doctor.is_active
                and doctor.check_password("Pass1234!")
            ):
                _done = True
                return
            call_command("seed_demo_users")
            _done = True
        except Exception:
            logger.exception("Demo account repair failed")
