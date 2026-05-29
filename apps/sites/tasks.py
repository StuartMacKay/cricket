import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task
def take_snapshots():
    """Trigger snapshots for all overdue enabled sites."""
    from sites.models import Site
    for site in Site.objects.overdue():
        take_site_snapshot.delay(site.pk)


@shared_task
def take_site_snapshot(site_pk: int):
    """Create a parent Snapshot and dispatch all audit tasks."""
    from headers.tasks import take_header_snapshot
    from lighthouse.tasks import take_lighthouse_snapshot
    from pageweight.tasks import take_weight_snapshot
    from sites.models import Site

    site = Site.objects.get(pk=site_pk)
    snapshot = site.create_snapshot()

    take_lighthouse_snapshot.delay(snapshot.pk)
    take_header_snapshot.delay(snapshot.pk)
    take_weight_snapshot.delay(snapshot.pk)
