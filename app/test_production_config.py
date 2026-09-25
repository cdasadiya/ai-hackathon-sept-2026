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
