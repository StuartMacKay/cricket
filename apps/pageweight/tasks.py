import logging

from celery import chord, group, shared_task

log = logging.getLogger(__name__)


@shared_task
def take_weight_scan(scan_pk: int):
    """Create a weight Run for a sites.Scan and measure all its pages."""
    from sites.models import Scan
    from .models import PageData, Run

    scan = Scan.objects.select_related("site").get(pk=scan_pk)

    run = Run.objects.create(scan=scan, status=Run.Status.RUNNING)

    page_pks = list(scan.pages.values_list("pk", flat=True))
    if not page_pks:
        run.status = Run.Status.COMPLETE
        run.page_count = 0
        run.save(update_fields=["status", "page_count"])
        return

    for pk in page_pks:
        PageData.objects.get_or_create(page_id=pk)

    chord(
        group(measure_page_weight.s(pk) for pk in page_pks),
        complete_weight_run.si(run.pk),
    ).delay()


@shared_task
def measure_page_weight(page_pk: int):
    from .models import PageData
    PageData.objects.get(page_id=page_pk).measure()


@shared_task
def complete_weight_run(run_pk: int):
    from .models import Run
    run = Run.objects.get(pk=run_pk)
    run.page_count = run.scan.pages.count()
    run.status = Run.Status.COMPLETE
    run.save(update_fields=["status", "page_count"])
