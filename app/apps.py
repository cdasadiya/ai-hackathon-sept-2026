import logging
import os
import sys

from django.apps import AppConfig as DjangoAppConfig

logger = logging.getLogger(__name__)


class AppConfig(DjangoAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        # Render often has no DATABASE_URL during build. Seed when the web
        # process starts so demo logins exist even if the start command is
        # only gunicorn.
        if not os.environ.get("DATABASE_URL"):
            return
        argv = " ".join(sys.argv)
        if any(
            flag in argv
            for flag in (
                "migrate",
                "makemigrations",
                "collectstatic",
                "test",
                "seed_demo_users",
                "seed_showcase",
                "shell",
            )
        ):
            return
        if not any(flag in argv for flag in ("gunicorn", "runserver")):
            return
        try:
            from django.contrib.auth import get_user_model
            from django.core.management import call_command

            # Demo admin/doctor/patient roster (Pass1234!). Independent of showcase.
            # Seed when any core demo login is missing, or admin1 password drifted.
            if os.environ.get("SEED_DEMO_USERS", "true").strip().lower() in {
                "1",
                "true",
                "t",
                "yes",
                "y",
                "on",
            }:
                User = get_user_model()
                needed = {"admin1", "patient1", "doctor1"}
                present = set(
                    User.objects.filter(username__in=needed).values_list("username", flat=True)
                )
                admin1 = User.objects.filter(username="admin1").first()
                password_ok = bool(admin1 and admin1.check_password("Pass1234!"))
                if needed - present or not password_ok:
                    call_command("seed_demo_users")

            # Shared APT-2026-90000x showcase dataset (Showcase123!). Always on
            # production starts unless SEED_SHOWCASE=false.
            if os.environ.get("SEED_SHOWCASE", "true").strip().lower() in {
                "1",
                "true",
                "t",
                "yes",
                "y",
                "on",
            }:
                call_command("seed_showcase")
        except Exception:
            logger.exception("Startup dataset seed failed")
