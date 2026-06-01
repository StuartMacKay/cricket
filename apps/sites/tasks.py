import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task
def take_scans():
    """Trigger scans for all overdue enabled sites."""
    from sites.models import Site
    for site in Site.objects.overdue():
        take_site_scan.delay(site.pk)


@shared_task
def take_site_scan(site_pk: int):
    """Create a Scan, build the shared page list, and dispatch enabled tool tasks."""
    from sites.models import Page, Site

    site = Site.objects.get(pk=site_pk)
    scan = site.create_scan()

    try:
        urls = list(site.get_urls())
    except Exception:
        log.exception("Failed to discover pages", extra={"site": site.slug})
        urls = []

    for url in urls:
        Page.objects.get_or_create(scan=scan, url=str(url))

    if site.enable_lighthouse:
        from lighthouse.tasks import take_lighthouse_scan
        take_lighthouse_scan.delay(scan.pk)

    if site.enable_headers:
        from headers.tasks import take_header_scan
        take_header_scan.delay(scan.pk)

    if site.enable_pageweight:
        from pageweight.tasks import take_weight_scan
        take_weight_scan.delay(scan.pk)
