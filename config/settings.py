"""
Django settings
https://docs.djangoproject.com/en/6.0/topics/settings/

"""

import os
import socket
import sys

from django.core.exceptions import ImproperlyConfigured

import environ  # type: ignore

# #######################
#   PROJECT DIRECTORIES
# #######################

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(PROJECT_DIR)
ROOT_DIR = os.path.dirname(BACKEND_DIR)
NODE_DIR = os.path.join(ROOT_DIR, "node")

sys.path.insert(0, os.path.join(BACKEND_DIR, "apps"))

# ###############
#   ENVIRONMENT
# ###############

env = environ.Env()

DJANGO_ENV = env.str("DJANGO_ENV", default="development")

if DJANGO_ENV not in ("development", "production"):
    raise ImproperlyConfigured(
        "Unknown environment name for settings: '%s'" % DJANGO_ENV
    )

DEBUG = env.bool("DJANGO_DEBUG", default=True)

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
    "django.contrib.sitemaps",
    "django_celery_beat",
    "django_celery_results",
    "django_json_widget",
    "watchman",
    "metrics",
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
        "debug_toolbar",
        "django_extensions",
    ]

    MIDDLEWARE = [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ] + MIDDLEWARE

# ##############
#   WEB SERVER
# ##############

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

if DEBUG:
    # From cookiecutter-django: We need to configure an IP address to
    # allow connections from, but in Docker we can't use 127.0.0.1 since
    # this runs in a container but we want to access the django_debug_toolbar
    # from our browser outside of the container.
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[: ip.rfind(".")] + ".1" for ip in ips] + [
        "127.0.0.1",
        "10.0.2.2",
    ]

WATCHMAN_TOKENS = env.str("DJANGO_WATCHMAN_TOKENS", None)

# ############
#   DATABASE
# ############

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

DATABASES = {
    "default": env.db_url(default="postgres://project:password@localhost:5432/project")
}

# ###########
#   CACHING
# ###########

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env.str("CACHE_URL", default="redis://localhost:6379/0"),
    }
}

# ############
#   SECURITY
# ############

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="<not-set>")

if DJANGO_ENV == "production" and SECRET_KEY == "<not-set>":
    raise ImproperlyConfigured("You must define a secret key for production")

ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"]
)

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
            os.path.join(PROJECT_DIR, "templates"),
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

STATICFILES_DIRS = [
    os.path.join(PROJECT_DIR, "static"),
]

# DJANGO_STATIC_HOST only needs to be set when using a CDN such as CloudFront
# to cache the files served by whitenoise.

STATIC_ROOT = env.str("DJANGO_STATIC_ROOT", default=os.path.join(ROOT_DIR, "static"))
STATIC_HOST = env.str("DJANGO_STATIC_HOST", default="")
STATIC_URL = STATIC_HOST + "/static/"

MEDIA_ROOT = env.str("DJANGO_MEDIA_ROOT", default=os.path.join(ROOT_DIR, "media"))
MEDIA_URL = "/media/"

# S3 storage options for serving uploaded files from an AWS S3 Bucket.
# The configure may differ for other S3 compatible service. For example,
# for Digital Ocean's Spaces service you need to set AWS_S3_REGION_NAME
# and AWS_S3_ENDPOINT_URL instead of AWS_S3_CUSTOM_DOMAIN.

AWS_ACCESS_KEY_ID = env.str("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env.str("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env.str("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_CUSTOM_DOMAIN = env.str("AWS_S3_CUSTOM_DOMAIN", default="")
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

STORAGES = {
    "default": {
        "BACKEND": env.str(
            "DJANGO_DEFAULT_STORAGE_BACKEND",
            default="django.core.files.storage.FileSystemStorage",
        ),
    },
    "staticfiles": {
        "BACKEND": env.str(
            "DJANGO_STATICFILES_BACKEND",
            default="django.contrib.staticfiles.storage.StaticFilesStorage",
        ),
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

LOG_LEVEL = env.str("DJANGO_LOG_LEVEL", default="INFO")

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

# #########
#   EMAIL
# #########

vars().update(env.email("DJANGO_EMAIL_URL", default="consolemail://"))

EMAIL_USE_SSL = env.bool("DJANGO_EMAIL_USE_SSL", default="True")

# ########
#   SITE
# ########

SITE_ID = env.int("DJANGO_SITE_ID", default=1)

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
