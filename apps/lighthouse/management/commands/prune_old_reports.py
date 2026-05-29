"""Management command to delete raw Lighthouse JSON reports older than 90 days.

The self-contained HTML report (html_report) is kept permanently.
Only the raw JSON report (report) is pruned.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from lighthouse.models import Page

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete raw Lighthouse JSON reports older than 90 days"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Number of days after which reports are pruned (default: 90)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - timedelta(days=days)

        pages = Page.objects.filter(created__lt=cutoff).exclude(report="")

        count = pages.count()
        self.stdout.write(f"Found {count} report(s) older than {days} days")

        if dry_run:
            self.stdout.write("Dry run — no files deleted")
            return

        deleted = 0
        for page in pages:
            if page.report:
                page.report.delete(save=False)
                page.report = None
                page.save(update_fields=["report"])
                deleted += 1

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} report(s)"))
