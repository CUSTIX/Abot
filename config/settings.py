"""Abot settings. Every environment-specific value comes from environment variables."""

import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Required: fail loudly at startup instead of running with a guessable key.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


def env_list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


DEBUG = env_bool("DJANGO_DEBUG")  # off unless explicitly turned on
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "")  # set by Render
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "accounts",
    "money",
    "planning",
    "utang",
    "paluwagan",
]

AUTH_USER_MODEL = "accounts.User"

# Public demo: the login screen offers the demo account; the demo user can't change its password.
DEMO_MODE = env_bool("DEMO_MODE")
DEMO_USERNAME = "demo"
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "abot-demo")
# Header (request.META key) with the real visitor IP, set by a proxy that overwrites it, e.g.
# HTTP_CF_CONNECTING_IP behind Cloudflare/Render. Empty: use the socket address. Never point it at
# X-Forwarded-For, which clients can forge. Used to rate-limit sign-in.
CLIENT_IP_HEADER = os.environ.get("CLIENT_IP_HEADER", "")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

# Strict CSP: the React build is plain files from 'self'; no inline scripts, no eval.
_FONT_CSS, _FONT_FILES = "https://fonts.googleapis.com", "https://fonts.gstatic.com"
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        f"style-src 'self' 'unsafe-inline' {_FONT_CSS}",
        f"font-src 'self' {_FONT_FILES}",
        "img-src 'self' data:",
        "connect-src 'self'",
        "manifest-src 'self'",
        "worker-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
PERMISSIONS_POLICY = (
    "camera=(), microphone=(), geolocation=(), payment=(), usb=(), browsing-topics=()"
)

# Session auth for the SPA (same origin): HttpOnly cookies, CSRF token fetched from /api/auth/csrf/
# and kept in memory by the app (the cookie itself is HttpOnly too).
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "COERCE_DECIMAL_TO_STRING": True,
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "signup": "5/hour"},
    "EXCEPTION_HANDLER": "core.api.exception_handler",
}
# Throttle counters live in Postgres (not process memory), so every worker shares them and the
# web container stays stateless. Table created by `createcachetable` (start script / compose).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "sahod_cache",
    }
}

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"


def database_from_url(url: str) -> dict:
    """postgres:// URL (what hosted Postgres such as Neon hands out) -> Django settings."""
    parts = urlsplit(url)
    if parts.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must start with postgres:// or postgresql://")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or ""),
        "OPTIONS": dict(parse_qsl(parts.query)),
    }


DATABASES = {
    "default": database_from_url(os.environ["DATABASE_URL"])
    if os.environ.get("DATABASE_URL")
    else {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "abot"),
        "USER": os.environ.get("POSTGRES_USER", "abot"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "Asia/Manila")  # paydays are local dates
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The React build (vite base "/static/") is collected like any other static files.
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
STATICFILES_DIRS = [FRONTEND_DIST] if FRONTEND_DIST.exists() else []
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if env_bool("DJANGO_STATIC_MANIFEST")
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
WHITENOISE_USE_FINDERS = not env_bool("DJANGO_STATIC_MANIFEST")
# Python's mimetypes table has no entry for .webmanifest, so WhiteNoise would serve the PWA
# manifest as application/octet-stream and browsers would refuse to install the app.
WHITENOISE_MIMETYPES = {".webmanifest": "application/manifest+json"}

if env_bool("DJANGO_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SILENCED_SYSTEM_CHECKS = ["security.W021"]  # HSTS preload is opt-in, hard to undo
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
