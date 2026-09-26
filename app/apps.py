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
            from .demo_accounts import ensure_demo_accounts

            # Repair admin1/doctor1/patient1 and showcase case_* accounts.
            # Ignores SEED_DEMO_USERS=false so a skipped start script cannot
            # leave the login form with an empty user table.
            ensure_demo_accounts()
        except Exception:
            logger.exception("Startup dataset seed failed")
