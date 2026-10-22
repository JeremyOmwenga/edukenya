"""
EduKenya settings.

Every value that differs between environments comes from an environment
variable. Locally they are read from .env (never committed); on AWS they are
injected by the runtime. When DJANGO_DEBUG is off, the guardrails at the bottom
of this file refuse to start the app if anything security-critical is missing.

Multi-tenancy (django-tenants): one PostgreSQL schema per school.
  public schema   -> landing page, school registration, super admin console
  school schemas  -> everything belonging to one school (its own users table,
                     sessions, and later lessons, grades, fees ...)
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, "1" if default else "0").strip().lower() in {"1", "true", "yes"}


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else None)

# ---------------------------------------------------------------------------
# Domains
# ---------------------------------------------------------------------------
# Root domain of the platform. Schools live on <subdomain>.<BASE_DOMAIN>.
# Locally this is "localhost": browsers resolve *.localhost to 127.0.0.1.
BASE_DOMAIN = env("EDUKENYA_BASE_DOMAIN", "localhost").lower()
SITE_SCHEME = env("EDUKENYA_SITE_SCHEME", "http" if DEBUG else "https")
SITE_PORT = env("EDUKENYA_SITE_PORT", ":8000" if DEBUG else "")  # e.g. ":8000"

# Only the root domain and its subdomains are ever served. Any other Host
# header is rejected before a view runs.
ALLOWED_HOSTS = [BASE_DOMAIN, f".{BASE_DOMAIN}"]

# Subdomains schools may never claim (platform use, look-alikes, mail records).
RESERVED_SUBDOMAINS = {
    "www", "admin", "administrator", "api", "app", "assets", "auth", "billing",
    "blog", "cdn", "console", "dashboard", "dev", "docs", "edukenya", "email",
    "ftp", "help", "imap", "login", "mail", "mx", "ns1", "ns2", "pay",
    "payments", "pop", "portal", "public", "root", "secure", "signup", "smtp",
    "staging", "static", "status", "support", "system", "test", "webmail",
}

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
SHARED_APPS = [
    "django_tenants",              # must be first
    "tenancy",                     # Client (school) + Domain models
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",                    # users table exists in public AND every school schema
    "onboarding",                  # school applications (public only)
    "console",                     # super admin console + audit log (public only)
    "landing",
]

TENANT_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "accounts",
    "school",                      # school-side pages (login, dashboard)
]

INSTALLED_APPS = list(SHARED_APPS) + [a for a in TENANT_APPS if a not in SHARED_APPS]
# NOTE: django.contrib.admin is deliberately NOT installed. Less attack surface;
# platform administration happens in the purpose-built console app.

TENANT_MODEL = "tenancy.Client"
TENANT_DOMAIN_MODEL = "tenancy.Domain"
PUBLIC_SCHEMA_NAME = "public"
PUBLIC_SCHEMA_URLCONF = "edukenya.urls_public"
ROOT_URLCONF = "edukenya.urls_tenant"
SHOW_PUBLIC_IF_NO_TENANT_FOUND = False  # unknown subdomain -> 404, never the public site

DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]

MIDDLEWARE = [
    # Resolves the school from the Host header and blocks schools that are not
    # active. Must run first so nothing else touches the wrong schema.
    "tenancy.middleware.TenantAccessMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "edukenya.security.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "edukenya.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "edukenya.wsgi.application"

# ---------------------------------------------------------------------------
# Database (PostgreSQL only: schemas are how schools are isolated)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": env("DB_NAME", "edukenya"),
        "USER": env("DB_USER", "edukenya"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": env("DB_SSLMODE", "prefer" if DEBUG else "require")},
    }
}

# Shared cache in the database (used for rate limiting). Keys are prefixed with
# the current schema so one school's counters never collide with another's.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "edukenya_cache",
        "KEY_FUNCTION": "django_tenants.cache.make_key",
        "REVERSE_KEY_FUNCTION": "django_tenants.cache.reverse_key",
    }
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"  # school subdomains; the console guards itself
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Sessions: host-only cookies (SESSION_COOKIE_DOMAIN stays None) so a login on
# school-a.<domain> is never sent to school-b.<domain> or the console.
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Email verification links for school applications expire after this long.
APPLICATION_VERIFY_MAX_AGE = 60 * 60 * 48

# Rate limits: (max attempts, window in seconds)
RATE_LIMITS = {
    "register_ip": (5, 60 * 60),
    "resend_ip": (5, 60 * 60),
    "resend_email": (3, 60 * 60),
    "login_ip": (10, 15 * 60),
    "login_account": (5, 15 * 60),
    "console_login_ip": (5, 15 * 60),
}

# Number of trusted reverse proxies in front of Django (ALB, Cloudflare...).
# 0 = use REMOTE_ADDR only (local). Never trust X-Forwarded-For blindly.
TRUSTED_PROXY_COUNT = int(env("TRUSTED_PROXY_COUNT", "0"))

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com",
    "img-src 'self' data:",
    "script-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "object-src 'none'",
])

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    # Only correct when a proxy we control (ALB) always sets this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    LANGUAGE_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # HSTS preload is a near-permanent browser-level commitment. Decide once the
    # final production domain is settled; until then this check is silenced on purpose.
    SILENCED_SYSTEM_CHECKS = ["security.W021"]

# ---------------------------------------------------------------------------
# Internationalisation: English (default) and Kiswahili
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", _("English")),
    ("sw", _("Kiswahili")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
TIME_ZONE = "Africa/Nairobi"
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Email via Amazon SES (API v2)
# ---------------------------------------------------------------------------
# Locally: credentials of the edukenya-ses-sender IAM user from .env.
# On AWS: leave them unset; boto3 picks up the IAM role automatically.
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", "django_ses.SESBackend")
USE_SES_V2 = True
AWS_SES_REGION_NAME = env("AWS_SES_REGION_NAME", "eu-west-1")
AWS_SES_ACCESS_KEY_ID = env("AWS_SES_ACCESS_KEY_ID") or None
AWS_SES_SECRET_ACCESS_KEY = env("AWS_SES_SECRET_ACCESS_KEY") or None
AWS_SES_CONFIGURATION_SET = env("AWS_SES_CONFIGURATION_SET", "edukenya-default")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", f"EduKenya <no-reply@{BASE_DOMAIN}>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Where "new school is waiting for approval" notices go.
PLATFORM_NOTIFY_EMAIL = env("PLATFORM_NOTIFY_EMAIL", "")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {
        "edukenya": {"handlers": ["console"], "level": "INFO"},
        "django.security": {"handlers": ["console"], "level": "WARNING"},
    },
}

# ---------------------------------------------------------------------------
# Production guardrails: refuse to boot with unsafe configuration
# ---------------------------------------------------------------------------
if not DEBUG:
    problems = []
    if not SECRET_KEY or len(SECRET_KEY) < 50 or SECRET_KEY.startswith("dev-only"):
        problems.append("DJANGO_SECRET_KEY must be set to a long random value")
    if BASE_DOMAIN in {"localhost", "127.0.0.1"} or "." not in BASE_DOMAIN:
        problems.append("EDUKENYA_BASE_DOMAIN must be the real public domain")
    if SITE_SCHEME != "https":
        problems.append("EDUKENYA_SITE_SCHEME must be https")
    if not DATABASES["default"]["PASSWORD"]:
        problems.append("DB_PASSWORD must be set")
    if DATABASES["default"]["OPTIONS"]["sslmode"] not in {"require", "verify-ca", "verify-full"}:
        problems.append("DB_SSLMODE must enforce TLS")
    if "console" in EMAIL_BACKEND or "locmem" in EMAIL_BACKEND:
        problems.append("DJANGO_EMAIL_BACKEND must send real email")
    if problems:
        raise ImproperlyConfigured("Unsafe production settings:\n - " + "\n - ".join(problems))
