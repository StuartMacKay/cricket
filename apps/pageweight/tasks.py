import logging

from celery import chord, group, shared_task

log = logging.getLogger(__name__)


@shared_task
def take_weight_run(job_pk: int):
    """Create a Run for a pageweight.Job and measure all its pages."""
    from .models import Job, Page, Run

    job = Job.objects.select_related("site").get(pk=job_pk)
    run = Run.objects.create(job=job, status=Run.Status.RUNNING)

    pks = []
    try:
        for url in job.get_urls():
            page, _ = Page.objects.get_or_create(run=run, url=str(url))
            pks.append(page.pk)
    except Exception:
        log.exception("Failed to discover pages", extra={"job": job_pk})
        run.status = Run.Status.FAILED
        run.save(update_fields=["status"])
        return

    if not pks:
        run.complete()
        return

    chord(
        group(measure_page_weight.s(pk) for pk in pks),
        complete_run.si(run.pk),
    ).delay()


@shared_task
def measure_page_weight(page_pk: int):
    from .models import Page
    Page.objects.get(pk=page_pk).measure()


@shared_task
def complete_run(run_pk: int):
    from .models import Run
    Run.objects.get(pk=run_pk).complete()
