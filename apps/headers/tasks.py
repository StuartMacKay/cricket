import logging

from celery import chord, group, shared_task

log = logging.getLogger(__name__)


@shared_task
def take_header_snapshot(sites_snapshot_pk: int):
    """Create a header Snapshot for a sites.Snapshot and audit all its pages."""
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
        log.exception("Failed to discover pages for header snapshot", extra={"site": site.slug})
        snapshot.status = Snapshot.Status.FAILED
        snapshot.save(update_fields=["status"])
        return

    if not pks:
        snapshot.status = Snapshot.Status.COMPLETE
        snapshot.page_count = 0
        snapshot.save(update_fields=["status", "page_count"])
        return

    chord(
        group(fetch_page_headers.s(pk) for pk in pks),
        complete_header_snapshot.si(snapshot.pk),
    ).delay()


@shared_task
def fetch_page_headers(page_pk: int):
    from .models import Page
    Page.objects.get(pk=page_pk).fetch()


@shared_task
def complete_header_snapshot(snapshot_pk: int):
    from .models import Snapshot
    snapshot = Snapshot.objects.get(pk=snapshot_pk)
    snapshot.page_count = snapshot.pages.count()
    snapshot.status = Snapshot.Status.COMPLETE
    snapshot.save(update_fields=["status", "page_count"])
