from celery import chain, chord, group, shared_task

from .models import Page, Site, Snapshot


@shared_task
def take_snapshots():
    for site in Site.objects.overdue():
        take_snapshot.delay(site.pk)


@shared_task
def take_snapshot(site_pk: int):
    snapshot = Site.objects.get(pk=site_pk).create_snapshot()
    chain(
        create_pages.s(snapshot.pk),
        audit_pages.s(snapshot.pk),
    ).delay()


@shared_task
def create_pages(snapshot_pk: int):
    Snapshot.objects.get(pk=snapshot_pk).create_pages()


@shared_task
def audit_pages(result, snapshot_pk: int):
    pks = list(Snapshot.objects.get(pk=snapshot_pk).get_page_keys())
    return chord(
        group(audit_page.s(pk) for pk in pks),
        chain(
            collect_metrics.si(snapshot_pk),
            publish_report.si(snapshot_pk),
        ),
    ).delay()


@shared_task
def audit_page(page_pk: int):
    Page.objects.get(pk=page_pk).audit()


@shared_task
def collect_metrics(snapshot_pk: int):
    Snapshot.objects.get(pk=snapshot_pk).collect_metrics()


@shared_task
def publish_report(snapshot_pk: int):
    Snapshot.objects.get(pk=snapshot_pk).publish_report()
