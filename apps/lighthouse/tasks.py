import logging

from celery import chord, group, shared_task

log = logging.getLogger(__name__)


@shared_task
def take_lighthouse_run(job_pk: int):
    """Create a Run for a lighthouse.Job, discover pages, and audit them."""
    import json
    import os
    import tempfile

    from .models import Job, Page, Run

    job  = Job.objects.select_related("site").get(pk=job_pk)
    site = job.site

    config = {"formFactor": job.platform}
    only   = job.get_only_categories()
    if only:
        config["onlyCategories"] = only

    lh_dir = os.path.join(tempfile.gettempdir(), "lighthouse-run")
    os.makedirs(lh_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", prefix=site.slug, suffix=".json", dir=lh_dir, delete=False
    ) as fp:
        json.dump(config, fp)
        config_file = fp.name

    run = Run.objects.create(
        job=job,
        status=Run.Status.RUNNING,
        config_file=config_file,
    )

    pks = []
    try:
        for url in job.get_urls():
            page, _ = Page.objects.get_or_create(run=run, url=str(url))
            pks.append(page.pk)
    except Exception:
        log.exception("Failed to discover pages", extra={"job": job_pk})
        run.delete_config_file()
        run.status = Run.Status.FAILED
        run.save(update_fields=["status"])
        return

    if not pks:
        run.complete()
        return

    chord(
        group(audit_page.s(pk) for pk in pks),
        complete_run.si(run.pk),
    ).apply_async(link_error=mark_failed.si(run.pk))


@shared_task(bind=True)
def audit_page(self, page_pk: int):
    from .models import Page
    Page.objects.get(pk=page_pk).audit()


@shared_task
def complete_run(run_pk: int):
    from .models import Run
    Run.objects.get(pk=run_pk).complete()


@shared_task
def mark_failed(run_pk: int):
    from .models import Run
    try:
        run = Run.objects.get(pk=run_pk)
        run.delete_config_file()
        run.status = Run.Status.FAILED
        run.save(update_fields=["status"])
    except Run.DoesNotExist:
        pass
