import logging

from celery import shared_task
from django.utils import timezone

log = logging.getLogger(__name__)


@shared_task
def check_overdue_jobs():
    """Trigger a new Run for every enabled Job whose crontab is overdue.

    Iterates all concrete BaseJob subclasses registered in INSTALLED_APPS.
    Each Job subclass defines TASK_NAME pointing to its collection task.
    """
    from django.apps import apps
    from sites.models import BaseJob

    now = timezone.now()
    triggered = 0

    for model in apps.get_models():
        if not (isinstance(model, type) and issubclass(model, BaseJob) and not model._meta.abstract):
            continue
        for job in model.objects.filter(enabled=True).exclude(crontab=""):
            if job.is_overdue(now):
                try:
                    job.trigger_run()
                    triggered += 1
                    log.info(
                        "Job triggered",
                        extra={"job": str(job), "task": job.TASK_NAME},
                    )
                except Exception:
                    log.exception("Failed to trigger job", extra={"job": str(job)})

    log.info("Overdue job check complete", extra={"triggered": triggered})
