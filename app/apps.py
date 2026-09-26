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
        if os.environ.get("SEED_DEMO_USERS", "true") != "true":
            return
        if not os.environ.get("DATABASE_URL"):
            return
        argv = " ".join(sys.argv)
        if any(flag in argv for flag in ("migrate", "makemigrations", "collectstatic", "test", "seed_demo_users", "seed_showcase", "shell")):
            return
        if not any(flag in argv for flag in ("gunicorn", "runserver")):
            return
        try:
            from django.contrib.auth import get_user_model
            from django.core.management import call_command

            if os.environ.get("SEED_DEMO_USERS", "true") == "true":
                existing = get_user_model().objects.filter(username="admin1").first()
                if existing is None or not existing.check_password("Pass1234!"):
                    call_command("seed_demo_users")
            call_command("seed_showcase")
        except Exception:
            logger.exception("Startup dataset seed failed")
