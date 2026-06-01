import logging

from celery import chain, chord, group, shared_task

log = logging.getLogger(__name__)


@shared_task
def take_lighthouse_scan(scan_pk: int):
    """Create a lighthouse Run for a sites.Scan and run the full audit pipeline."""
    import json
    import os
    import tempfile

    from sites.models import Scan
    from .models import Run

    scan = Scan.objects.select_related("site").get(pk=scan_pk)
    site = scan.site

    config = {**site.extra_config, "formFactor": site.platform}
    tmpdir = tempfile.gettempdir()
    lh_dir = os.path.join(tmpdir, "lighthouse-run")
    os.makedirs(lh_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", prefix=site.slug, suffix=".json", dir=lh_dir, delete=False
    ) as fp:
        json.dump(config, fp)
        config_file = fp.name

    run = Run.objects.create(
        scan=scan,
        status=Run.Status.RUNNING,
        config_file=config_file,
    )

    mark_failed_task = mark_failed.si(run.pk)
    chain(
        audit_pages.s(run.pk),
        complete_run.s(run.pk),
    ).on_error(mark_failed_task).delay()


@shared_task
def audit_pages(result, run_pk: int):
    from .models import Run
    pks = list(Run.objects.get(pk=run_pk).get_page_keys())
    return chord(
        group(audit_page.s(pk) for pk in pks),
        complete_run.si(run_pk),
    ).delay()


@shared_task(bind=True)
def audit_page(self, page_pk: int):
    from sites.models import Page
    from .models import PageResult

    page = Page.objects.get(pk=page_pk)
    page_result, _ = PageResult.objects.get_or_create(
        page=page,
        defaults={"audited": False},
    )
    page_result.audit()


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
        run.scan.status = "failed"
        run.scan.save(update_fields=["status"])
    except Run.DoesNotExist:
        pass
