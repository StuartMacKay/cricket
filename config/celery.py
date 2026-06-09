import os

from celery import Celery  # type: ignore
from celery.schedules import crontab
from celery.signals import setup_logging  # type: ignore
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery()


class CeleryConfig:
    # Configure logging using Django's LOGGING setting. Caveat: since logging
    # is configured using the setup_logging signal, see below, this might not
    # be needed.
    worker_hijack_root_logger = False

    broker_url = "redis://redis:6379/1"

    # Store the results from the tasks in the database. They will be deleted
    # by celery after one day.
    result_backend = "django-db"
    result_extended = True


# Load the configuration
app.config_from_object(CeleryConfig)
# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.task_queues = [
    Queue("sites", Exchange("sites"), routing_key="sites"),
    Queue("pages", Exchange("pages"), routing_key="pages"),
]

app.conf.task_queue_max_priority = 10
app.conf.task_default_priority = 5
app.conf.task_default_queue = "pages"

# Check for overdue Jobs every 5 minutes. Jobs with well-defined schedules
# (e.g. first of month, Monday mornings) will be triggered within 5 minutes
# of their due time.
app.conf.beat_schedule = {
    "check-overdue-jobs": {
        "task": "audits.tasks.overdue_jobs",
        "schedule": crontab(minute="*/5"),
    },
}

app.conf.task_routes = {
    "audits.tasks.overdue_jobs": {"queue": "sites"},
    "audits.tasks.job_run": {"queue": "sites"},
    "audit.tasks.audit_page": {"queue": "pages"},
    "audit.tasks.page_headers": {"queue": "pages"},
    "audit.tasks.page_weights": {"queue": "pages"},
    "audits.tasks.lighthouse_audit": {"queue": "pages"},
}


@setup_logging.connect
def receiver_setup_logging(loglevel, logfile, format, colorize, **kwargs):  # noqa
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)
