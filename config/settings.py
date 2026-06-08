"""
Django settings
https://docs.djangoproject.com/en/6.0/topics/settings/

"""

import environ  # type: ignore
import os
import sys
from django.core.exceptions import ImproperlyConfigured

# #######################
#   PROJECT DIRECTORIES
# #######################

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CONFIG_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")
NODE_DIR = os.path.join(ROOT_DIR, "node")

sys.path.insert(0, os.path.join(ROOT_DIR, "apps"))

# ###############
#   ENVIRONMENT
# ###############

env = environ.Env()

DJANGO_ENV = env.str("DJANGO_ENV")

if DJANGO_ENV not in ("development", "production"):
    raise ImproperlyConfigured(
        "Unknown environment name for settings: '%s'" % DJANGO_ENV
    )

DEBUG = env.bool("DJANGO_DEBUG")

if DJANGO_ENV == "production" and DEBUG:
    raise ImproperlyConfigured("'DEBUG = True' is not allowed in production")

# #####################
#   APPS & MIDDLEWARE
# #####################

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    "django_celery_results",
    "django_json_widget",
    "watchman",
    "audits",
    "api",
    "pages"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if DJANGO_ENV == "development" and DEBUG:
    INSTALLED_APPS += [
        "django_extensions",
    ]

# ##############
#   WEB SERVER
# ##############

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"


WATCHMAN_TOKENS = env.str("DJANGO_WATCHMAN_TOKENS", None)

# ############
#   DATABASE
# ############

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": f"{DATA_DIR}/db.sqlite3",
    }
}

# ###########
#   CACHING
# ###########

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379/0",
    }
}

# ############
#   SECURITY
# ############

SECRET_KEY = env.str("DJANGO_SECRET_KEY")

if DJANGO_ENV == "production" and SECRET_KEY == "<not-set>":
    raise ImproperlyConfigured("You must define a secret key for production")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",  # noqa
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# Basic security settings. We're not going to deal with HSTS settings, at least
# for now since there is nothing that specifically needs protecting.

# Redirect HTTP requests to HTTPS, but only in production
SECURE_SSL_REDIRECT = DJANGO_ENV == "production"
# Trust the X-Forwarded-Proto header set by Coolify's Traefik proxy so Django
# knows the original request was HTTPS even though Traefik forwards it as HTTP.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Set the "X-Content-Type-Options: nosniff" header if it is not set already.
SECURE_CONTENT_TYPE_NOSNIFF = True
# Don't send the session cookie unless the connection is secure.
SESSION_COOKIE_SECURE = True
# Tell the browser not to allow access to the cookie via javascript.
SESSION_COOKIE_HTTPONLY = True
# Don't send the CSRF cookie unless the connection is secure.
CSRF_COOKIE_SECURE = True

# #############
#   TEMPLATES
# #############

# The configuration will use the filesystem and app_directories loaders
# by default and enable the caching loader in production.

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(ROOT_DIR, "templates"),
        ],
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

if DJANGO_ENV == "production":
    TEMPLATES[0]["APP_DIRS"] = False
    TEMPLATES[0]["OPTIONS"]["loaders"] = [  # type: ignore
        (
            "django.template.loaders.cached.Loader",
            [
                "django_spaceless_templates.loaders.filesystem.Loader",
                "django_spaceless_templates.loaders.app_directories.Loader",
            ],
        )
    ]


# ########################
#   INTERNATIONALIZATION
# ########################

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ##########################
#   STATIC AND MEDIA FILES
# ##########################
# Static files are ALWAYS served from the local filesystem, whether in
# development or production. Serving files from a CDN such as CloudFront
# is then simply a matter of setting DJANGO_STATIC_HOST to the CloudFront
# domain. Media files can be served from local, network or remote storage
# according to the scale of the deployment. Most articles describing how
# to configure Django to use Amazon's S3 service start with serving up
# static files. If you do that with when using whitenoise then you lose
# the ability to create a manifest or compress the files. They are simply
# copied out to the S3 Bucket and served from there. In addition, serving
# static files from the local filesystem solves a problem when you have
# multiple servers with a load balancer. At some point during a deployment
# collectstatic needs to be run, but unless you designate one of the
# servers as the one responsible for doing it, they will either all
# compete to upload the files to remote storage, possibly corrupting the
# files, or you'll end up doing the uploads multiple times.

STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATIC_ROOT = os.path.join(ROOT_DIR, "static")
STATIC_URL = "/static/"

MEDIA_ROOT = os.path.join(ROOT_DIR, "media")
MEDIA_URL = "/media/"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage"
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# ###########
#   LOGGING
# ###########

# In general (production, staging, test) log everything to the console and
# leave the decision on where to store the messages to the environment in
# which Django is running, see https://12factor.net/logs.
#
# The same logging configuration is used for development and production
# since it's important to know if the logging is actually effective in
# advance of it being deployed. For browsing log files https://lnav.org
# is a great tool.

LOG_LEVEL = env.str("DJANGO_LOG_LEVEL")

if LOG_LEVEL not in ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"):
    raise ImproperlyConfigured("Unknown level for logging: " + LOG_LEVEL)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "django": {
            "level": "ERROR",
            "handlers": ["stdout"],
            "propagate": False,
        },
        "": {
            "handlers": ["stdout"],
            "level": LOG_LEVEL,
        },
    },
}

# ##########
#   SENTRY
# ##########

if DSN := env.str("DJANGO_SENTRY_DSN", default=""):
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(  # type: ignore
        DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
    )

# Move the Django Admin to somewhere obscure. This more about reducing
# the load on the server, created by break-in attempts and very little
# to do with security. You can deploy something like django-admin-honeypot
# at the regular /admin/ path and ban persistent offenders, though that
# is likely to be a never-ending task.
ADMIN_PATH = env.str("DJANGO_ADMIN_PATH", default="admin/")

if ADMIN_PATH[-1] != "/":
    ADMIN_PATH += "/"

# #####################
#   DJANGO EXTENSIONS
# #####################

if DJANGO_ENV == "development":
    SHELL_PLUS = "ipython"
