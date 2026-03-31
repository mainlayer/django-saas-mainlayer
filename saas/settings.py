import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-me-in-production")

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "accounts",
    "billing",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "saas.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "saas.wsgi.application"

# Database
_database_url = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
DATABASES = {
    "default": dj_database_url.parse(_database_url, conn_max_age=600)
}

# Custom user model
AUTH_USER_MODEL = "accounts.User"

# Auth redirects
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Mainlayer billing
MAINLAYER_API_KEY = os.environ.get("MAINLAYER_API_KEY", "")
MAINLAYER_RESOURCE_ID_FREE = os.environ.get("MAINLAYER_RESOURCE_ID_FREE", "")
MAINLAYER_RESOURCE_ID_PRO = os.environ.get("MAINLAYER_RESOURCE_ID_PRO", "")
MAINLAYER_RESOURCE_ID_ENTERPRISE = os.environ.get("MAINLAYER_RESOURCE_ID_ENTERPRISE", "")

MAINLAYER_PLANS = {
    "free": {
        "name": "Free",
        "resource_id": MAINLAYER_RESOURCE_ID_FREE,
        "price": 0,
        "features": ["5 projects", "1 GB storage", "Community support"],
    },
    "pro": {
        "name": "Pro",
        "resource_id": MAINLAYER_RESOURCE_ID_PRO,
        "price": 29,
        "features": ["Unlimited projects", "50 GB storage", "Priority support", "API access", "Advanced analytics"],
    },
    "enterprise": {
        "name": "Enterprise",
        "resource_id": MAINLAYER_RESOURCE_ID_ENTERPRISE,
        "price": 99,
        "features": [
            "Everything in Pro",
            "500 GB storage",
            "Dedicated support",
            "SSO / SAML",
            "Custom integrations",
            "SLA guarantee",
        ],
    },
}
