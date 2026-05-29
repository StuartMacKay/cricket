import logging

from celery import chain, chord, group, shared_task

from .models import Page, Site, Snapshot

log = logging.getLogger(__name__)


@shared_task
def take_snapshots():
    for site in Site.objects.overdue():
        take_site_snapshot.delay(site.pk)


@shared_task
def take_site_snapshot(site_pk: int):
    """Coordinate all audit types for a single site."""
    from headers.tasks import take_header_snapshot
    from pageweight.tasks import take_weight_snapshot

    take_snapshot.delay(site_pk)
    take_header_snapshot.delay(site_pk)
    take_weight_snapshot.delay(site_pk)


@shared_task
def take_snapshot(site_pk: int, snapshot_pk: int | None = None):
    if snapshot_pk is None:
        snapshot = Site.objects.get(pk=site_pk).create_snapshot()
    else:
        snapshot = Snapshot.objects.get(pk=snapshot_pk)
    snapshot.status = Snapshot.Status.RUNNING
    snapshot.save(update_fields=["status"])

    mark_failed_task = mark_failed.si(snapshot.pk)
    chain(
        create_pages.s(snapshot.pk),
        audit_pages.s(snapshot.pk),
    ).on_error(mark_failed_task).delay()


@shared_task
def create_pages(snapshot_pk: int):
    Snapshot.objects.get(pk=snapshot_pk).create_pages()


@shared_task
def audit_pages(result, snapshot_pk: int):
    pks = list(Snapshot.objects.get(pk=snapshot_pk).get_page_keys())
    return chord(
        group(audit_page.s(pk) for pk in pks),
        collect_metrics.si(snapshot_pk),
    ).delay()


@shared_task(bind=True)
def audit_page(self, page_pk: int):
    Page.objects.get(pk=page_pk).audit()


@shared_task
def collect_metrics(snapshot_pk: int):
    snapshot = Snapshot.objects.get(pk=snapshot_pk)
    snapshot.collect_metrics()

    # Update the site's current_snapshot pointer
    from .models import Site
    Site.objects.filter(pk=snapshot.site_id).update(current_snapshot=snapshot)


@shared_task
def mark_failed(snapshot_pk: int):
    """Mark a snapshot as failed and clean up its config file.

    Called as a Celery error link so the snapshot is marked failed
    even when the audit pipeline errors out mid-run.
    """
    try:
        snapshot = Snapshot.objects.get(pk=snapshot_pk)
        snapshot.delete_config_file()
        snapshot.status = Snapshot.Status.FAILED
        snapshot.save(update_fields=["status"])
    except Snapshot.DoesNotExist:
        pass
