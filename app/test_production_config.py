"""Production deployment settings and static asset checks."""
from pathlib import Path

from django.conf import settings
from django.test import Client, SimpleTestCase
from django.urls import reverse


class ProductionConfigTests(SimpleTestCase):
    def test_staticfiles_dirs_includes_project_static(self):
        dirs = [Path(d).resolve() for d in settings.STATICFILES_DIRS]
        self.assertIn((settings.BASE_DIR / "static").resolve(), dirs)

    def test_nexus_theme_source_exists(self):
        path = settings.BASE_DIR / "static" / "css" / "nexus-theme.css"
        self.assertTrue(path.is_file(), "static/css/nexus-theme.css must exist for collectstatic")

    def test_collectstatic_includes_admin_and_theme(self):
        from django.core.management import call_command

        call_command("collectstatic", interactive=False, verbosity=0)
        root = settings.STATIC_ROOT
        self.assertTrue((root / "admin" / "css" / "base.css").is_file())
        self.assertTrue((root / "css" / "nexus-theme.css").is_file())


class AuthTemplateTests(SimpleTestCase):
    def test_register_page_inlines_auth_styles(self):
        response = Client().get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("nx-auth-page", content)
        self.assertIn("--nx-brand", content)
        self.assertIn("Create your account", content)

    def test_login_page_inlines_auth_styles(self):
        response = Client().get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("--nx-brand", response.content.decode())
