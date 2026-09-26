from pathlib import Path
import os
from datetime import timedelta
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ImproperlyConfigured(f"Invalid boolean value for {name}: {value!r}")

def get_list_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]

DEBUG = get_bool_env("DEBUG", False)

SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("DJANGO_SECRET_KEY") or "dev-insecure-secret-key-only-for-local-debug"

def _default_allowed_hosts() -> str:
    hosts = [".onrender.com", "localhost", "127.0.0.1"]
    render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host and render_host not in hosts:
        hosts.append(render_host)
    return ",".join(hosts)


def _default_csrf_origins() -> str:
    # Django requires exact origins (no wildcards). Render sets RENDER_EXTERNAL_URL at runtime.
    origins = ["http://localhost:8000", "http://127.0.0.1:8000"]
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_url:
        origins.append(render_url)
    else:
        origins.append("https://ai-hackathon-sept-2026.onrender.com")
    return ",".join(origins)


ALLOWED_HOSTS = get_list_env("ALLOWED_HOSTS", _default_allowed_hosts())
CSRF_TRUSTED_ORIGINS = get_list_env("CSRF_TRUSTED_ORIGINS", _default_csrf_origins())

HEALTHZ_RUN_MIGRATIONS = get_bool_env("HEALTHZ_RUN_MIGRATIONS", False)

if not DEBUG:
    SECURE_SSL_REDIRECT = get_bool_env("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_PRELOAD = get_bool_env("SECURE_HSTS_PRELOAD", True)
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool_env("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    # Plain HTTP (Docker Compose, CI) must opt out. Render leaves these unset.
    SESSION_COOKIE_SECURE = get_bool_env("SESSION_COOKIE_SECURE", True)
    CSRF_COOKIE_SECURE = get_bool_env("CSRF_COOKIE_SECURE", True)

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework.authtoken", "app",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
IS_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")
REQUIRE_POSTGRES = get_bool_env("REQUIRE_POSTGRES", False)
if REQUIRE_POSTGRES and not IS_POSTGRES:
    raise ImproperlyConfigured(
        "PostgreSQL is required for this deployment. Set DATABASE_URL to a postgres connection string."
    )
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        ssl_require=(not DEBUG and IS_POSTGRES),
    )
}
AUTH_PASSWORD_VALIDATORS = [{"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},{"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},{"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},{"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"}]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        # CompressedStaticFilesStorage serves compressed files without a manifest.
        # We avoid CompressedManifestStaticFilesStorage because its staticfiles.json
        # can go stale on Render's ephemeral filesystem, causing a 500 on /admin/login/.
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "app.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # JWT is first so unauthenticated API calls receive 401 with a Bearer
        # challenge. Session authentication remains available for the browser.
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

# ── JWT Configuration ─────────────────────────────────────────────────────────
# Default lifetime values. These can be overridden at runtime via
# IntegrationConfig.jwt_access_token_lifetime_minutes.
_JWT_ACCESS_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", "60"))
_JWT_REFRESH_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_LIFETIME_DAYS", "30"))

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=_JWT_ACCESS_MINUTES),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=_JWT_REFRESH_DAYS),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# ── Legacy webhook env vars (kept for backward compat; moved to IntegrationConfig) ──
# These are read by call_post_upload_api() as a fallback when n8n is not configured.
POST_UPLOAD_WEBHOOK_URL = os.getenv("POST_UPLOAD_WEBHOOK_URL", "")
POST_UPLOAD_WEBHOOK_TOKEN = os.getenv("POST_UPLOAD_WEBHOOK_TOKEN", "")
