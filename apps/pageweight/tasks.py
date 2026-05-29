import logging

from celery import chord, group, shared_task

from lighthouse.models import Site

from .models import PageWeight, WeightSnapshot

log = logging.getLogger(__name__)


@shared_task
def take_weight_snapshots():
    """Trigger page weight snapshots for all overdue enabled sites."""
    for site in Site.objects.overdue():
        take_weight_snapshot.delay(site.pk)


@shared_task
def take_weight_snapshot(site_pk: int, platform: str = "mobile"):
    """Create a WeightSnapshot for a site and measure all its pages."""
    site = Site.objects.get(pk=site_pk)
    snapshot = WeightSnapshot.objects.create(
        site=site,
        platform=platform,
        status=WeightSnapshot.Status.RUNNING,
    )
    pks = []
    try:
        for url in site.get_urls():
            page = PageWeight.objects.create(snapshot=snapshot, url=str(url))
            pks.append(page.pk)
    except Exception:
        log.exception("Failed to discover pages for weight snapshot", extra={"site": site.slug})
        snapshot.status = WeightSnapshot.Status.FAILED
        snapshot.save(update_fields=["status"])
        return

    if not pks:
        snapshot.status = WeightSnapshot.Status.COMPLETE
        snapshot.page_count = 0
        snapshot.save(update_fields=["status", "page_count"])
        return

    chord(
        group(measure_page_weight.s(pk) for pk in pks),
        complete_weight_snapshot.si(snapshot.pk),
    ).delay()


@shared_task
def measure_page_weight(page_pk: int):
    """Run the Puppeteer measurement for a single page."""
    PageWeight.objects.get(pk=page_pk).measure()


@shared_task
def complete_weight_snapshot(snapshot_pk: int):
    """Mark a weight snapshot complete after all pages have been measured."""
    snapshot = WeightSnapshot.objects.get(pk=snapshot_pk)
    snapshot.page_count = snapshot.pages.count()
    snapshot.status = WeightSnapshot.Status.COMPLETE
    snapshot.save(update_fields=["status", "page_count"])
