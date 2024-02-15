import os

from celery import Celery  # type: ignore
from celery.schedules import crontab
from celery.signals import setup_logging  # type: ignore
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

app = Celery()


class CeleryConfig:
    # Configure logging using Django's LOGGING setting. Caveat: since logging
    # is configured using the setup_logging signal, see below, this might not
    # be needed.
    worker_hijack_root_logger = False

    # The default, unless it is overridden using an environment variable
    # is to assume we are running the demo using a virtualenv and connect
    # to a locally install instance of rabbitmq. When using containers,
    # the broker url will be set to connect to the rabbitmq service.
    broker_url = os.environ.get(
        "BROKER_URL", "amqp://guest:guest@localhost:5672/project"
    )

    # Store the results from the tasks in the database. They will be deleted
    # by celery after one day.
    result_backend = "django-db"
    result_extended = True


# Load the configuration
app.config_from_object(CeleryConfig)
# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.task_queues = [
    Queue(
        "sites",
        Exchange("sites"),
        routing_key="sites",
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "pages",
        Exchange("pages"),
        routing_key="pages",
        queue_arguments={"x-max-priority": 10},
    ),
]

app.conf.task_queue_max_priority = 10
app.conf.task_default_priority = 5
app.conf.task_default_queue = "pages"

# Snapshots may be scheduled to run at a precise time (to the minute), but
# since the code checks for snapshots that are overdue we can simply run
# the task every hour, at the risk of swamping the workers
app.conf.beat_schedule = {
    "take-snapshots": {
        "task": "metrics.tasks.take_snapshots",
        "schedule": crontab(minute="0"),  # every hour, on the hour
    },
}

app.conf.task_routes = {"metrics.tasks.take_snapshots": {"queue": "sites"}}


@setup_logging.connect
def receiver_setup_logging(loglevel, logfile, format, colorize, **kwargs):  # noqa
    from logging.config import dictConfig

    from django.conf import settings

    dictConfig(settings.LOGGING)
