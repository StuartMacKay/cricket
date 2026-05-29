import logging

from celery import chord, group, shared_task

from lighthouse.models import Site

from .models import HeaderSnapshot, PageHeaders

log = logging.getLogger(__name__)


@shared_task
def take_header_snapshots():
    """Trigger header snapshots for all overdue enabled sites."""
    for site in Site.objects.overdue():
        take_header_snapshot.delay(site.pk)


@shared_task
def take_header_snapshot(site_pk: int):
    """Create a HeaderSnapshot for a site and audit all its pages."""
    site = Site.objects.get(pk=site_pk)
    snapshot = HeaderSnapshot.objects.create(site=site, status=HeaderSnapshot.Status.RUNNING)
    pks = []
    try:
        for url in site.get_urls():
            page = PageHeaders.objects.create(snapshot=snapshot, url=str(url))
            pks.append(page.pk)
    except Exception as exc:
        log.exception("Failed to discover pages for header snapshot", extra={"site": site.slug})
        snapshot.status = HeaderSnapshot.Status.FAILED
        snapshot.save(update_fields=["status"])
        return

    if not pks:
        snapshot.status = HeaderSnapshot.Status.COMPLETE
        snapshot.page_count = 0
        snapshot.save(update_fields=["status", "page_count"])
        return

    chord(
        group(fetch_page_headers.s(pk) for pk in pks),
        complete_header_snapshot.si(snapshot.pk),
    ).delay()


@shared_task
def fetch_page_headers(page_pk: int):
    """Fetch HTTP headers for a single page."""
    PageHeaders.objects.get(pk=page_pk).fetch()


@shared_task
def complete_header_snapshot(snapshot_pk: int):
    """Mark a header snapshot as complete after all pages have been fetched."""
    snapshot = HeaderSnapshot.objects.get(pk=snapshot_pk)
    snapshot.page_count = snapshot.pages.count()
    snapshot.status = HeaderSnapshot.Status.COMPLETE
    snapshot.save(update_fields=["status", "page_count"])
