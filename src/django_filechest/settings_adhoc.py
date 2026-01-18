"""
Adhoc settings for django-filechest.

This settings module is used for quick, standalone usage with:
    uvx django-filechest /path/to/directory
    uvx django-filechest s3://bucket/prefix

"""

import os

from .settings import *  # noqa: F403


SECRET_KEY = "adhoc-insecure-key-not-for-production"

DEBUG = False

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "filechest",
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


ROOT_URLCONF = "django_filechest.urls_adhoc"

# Temporary database (set by __main__.py)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ["FILECHEST_DB_PATH"],
    }
}

# Adhoc mode: all users get editor access without authentication
FILECHEST_ADHOC_MODE = True
SESSION_COOKIE_NAME = "filechest_adhoc_session"
