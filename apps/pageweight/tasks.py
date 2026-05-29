import logging

from celery import chord, group, shared_task

log = logging.getLogger(__name__)


@shared_task
def take_weight_snapshot(sites_snapshot_pk: int):
    """Create a weight Snapshot for a sites.Snapshot and measure all its pages."""
    from sites.models import Snapshot as SiteSnapshot

    from .models import Page, Snapshot

    sites_snapshot = SiteSnapshot.objects.select_related("site").get(pk=sites_snapshot_pk)
    site = sites_snapshot.site

    snapshot = Snapshot.objects.create(snapshot=sites_snapshot, status=Snapshot.Status.RUNNING)
    pks = []
    try:
        for url in site.get_urls():
            page = Page.objects.create(snapshot=snapshot, url=str(url))
            pks.append(page.pk)
    except Exception:
        log.exception("Failed to discover pages for weight snapshot", extra={"site": site.slug})
        snapshot.status = Snapshot.Status.FAILED
        snapshot.save(update_fields=["status"])
        return

    if not pks:
        snapshot.status = Snapshot.Status.COMPLETE
        snapshot.page_count = 0
        snapshot.save(update_fields=["status", "page_count"])
        return

    chord(
        group(measure_page_weight.s(pk) for pk in pks),
        complete_weight_snapshot.si(snapshot.pk),
    ).delay()


@shared_task
def measure_page_weight(page_pk: int):
    from .models import Page
    Page.objects.get(pk=page_pk).measure()


@shared_task
def complete_weight_snapshot(snapshot_pk: int):
    from .models import Snapshot
    snapshot = Snapshot.objects.get(pk=snapshot_pk)
    snapshot.page_count = snapshot.pages.count()
    snapshot.status = Snapshot.Status.COMPLETE
    snapshot.save(update_fields=["status", "page_count"])
