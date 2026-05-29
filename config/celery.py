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

    broker_url = os.environ.get("BROKER_URL", "redis://localhost:6379/1")

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

# Snapshots may be scheduled to run at a precise time (to the minute), but
# since the code checks for snapshots that are overdue we can simply run
# the task every hour, at the risk of swamping the workers
app.conf.beat_schedule = {
    "take-snapshots": {
        "task": "sites.tasks.take_snapshots",
        "schedule": crontab(minute="0"),  # every hour, on the hour
    },
}

app.conf.task_routes = {
    "sites.tasks.take_snapshots": {"queue": "sites"},
    "sites.tasks.take_site_snapshot": {"queue": "sites"},
    "lighthouse.tasks.take_lighthouse_snapshot": {"queue": "sites"},
}


@setup_logging.connect
def receiver_setup_logging(loglevel, logfile, format, colorize, **kwargs):  # noqa
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)
