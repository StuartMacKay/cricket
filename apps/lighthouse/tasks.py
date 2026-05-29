import logging

from celery import chain, chord, group, shared_task

log = logging.getLogger(__name__)


@shared_task
def take_lighthouse_snapshot(sites_snapshot_pk: int):
    """Create a lighthouse Snapshot for a sites.Snapshot and run the full audit pipeline."""
    import json
    import os
    import tempfile

    from sites.models import Snapshot as SiteSnapshot
    from .models import Snapshot

    sites_snapshot = SiteSnapshot.objects.select_related("site").get(pk=sites_snapshot_pk)
    site = sites_snapshot.site

    # Build config file
    config = {**site.extra_config, "formFactor": site.platform}
    tmpdir = tempfile.gettempdir()
    lh_dir = os.path.join(tmpdir, "lighthouse-snapshot")
    os.makedirs(lh_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", prefix=site.slug, suffix=".json", dir=lh_dir, delete=False
    ) as fp:
        json.dump(config, fp)
        config_file = fp.name

    snapshot = Snapshot.objects.create(
        snapshot=sites_snapshot,
        status=Snapshot.Status.RUNNING,
        config_file=config_file,
    )

    mark_failed_task = mark_failed.si(snapshot.pk)
    chain(
        create_pages.s(snapshot.pk),
        audit_pages.s(snapshot.pk),
    ).on_error(mark_failed_task).delay()


@shared_task
def create_pages(snapshot_pk: int):
    from .models import Snapshot
    Snapshot.objects.get(pk=snapshot_pk).create_pages()


@shared_task
def audit_pages(result, snapshot_pk: int):
    from .models import Snapshot
    pks = list(Snapshot.objects.get(pk=snapshot_pk).get_page_keys())
    return chord(
        group(audit_page.s(pk) for pk in pks),
        collect_metrics.si(snapshot_pk),
    ).delay()


@shared_task(bind=True)
def audit_page(self, page_pk: int):
    from .models import Page
    Page.objects.get(pk=page_pk).audit()


@shared_task
def collect_metrics(snapshot_pk: int):
    from .models import Snapshot
    Snapshot.objects.get(pk=snapshot_pk).collect_metrics()


@shared_task
def mark_failed(snapshot_pk: int):
    from .models import Snapshot
    try:
        snapshot = Snapshot.objects.get(pk=snapshot_pk)
        snapshot.delete_config_file()
        snapshot.status = Snapshot.Status.FAILED
        snapshot.save(update_fields=["status"])
        # Also mark the parent failed
        snapshot.snapshot.status = "failed"
        snapshot.snapshot.save(update_fields=["status"])
    except Snapshot.DoesNotExist:
        pass
