import json
import os
import pathlib
import tempfile

from django.db import models
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel


class Snapshot(TimeStampedModel, models.Model):
    class Meta:
        verbose_name = _("Snapshot")
        verbose_name_plural = _("Snapshots")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED = "failed", _("Failed")

    site = models.ForeignKey(
        "Site",
        models.CASCADE,
        related_name="snapshots",
        verbose_name=_("Site"),
        help_text=_("The Site this Snapshot was created from"),
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Status"),
        db_index=True,
    )

    platform = models.CharField(
        max_length=20,
        default="mobile",
        verbose_name=_("Platform"),
        help_text=_("Emulation platform: 'mobile' or 'desktop'"),
    )

    page_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Page count"),
        help_text=_("Total number of pages audited; populated when complete"),
    )

    # Temporary path to the Lighthouse config JSON file; cleared after audits finish.
    config_file = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Config file"),
        help_text=_("Temporary path to the Lighthouse config file"),
    )

    webhook_url = models.URLField(
        verbose_name=_("Webhook URL"),
        help_text=_("Optional URL to POST to when the snapshot completes"),
        blank=True,
    )

    def __str__(self):
        return "{} ({})".format(self.site.name, self.created.strftime("%Y-%m-%d"))

    def create_pages(self):
        from .page import Page
        for url in self.site.get_urls():
            Page.objects.get_or_create(url=str(url), audited=False, snapshot=self)

    def get_page_keys(self):
        return self.pages.all().values_list("pk", flat=True)

    def get_number_of_pages(self) -> int:
        return int(self.pages.all().count())

    def delete_config_file(self):
        if self.config_file:
            path = pathlib.Path(self.config_file)
            if path.exists() and path.is_file():
                path.unlink()
            self.config_file = ""
            self.save(update_fields=["config_file"])

    def collect_metrics(self):
        """Aggregate PageCategory/PageAudit rows into SnapshotCategory/SnapshotAudit."""
        from django.db.models import Avg, Count, Q

        from .audit import (
            AuditDefinition,
            PageAudit,
            PageCategory,
            SnapshotAudit,
            SnapshotCategory,
        )
        from .rating import Rating

        pages_qs = self.pages.filter(audited=True)

        # Aggregate categories
        cat_agg = (
            PageCategory.objects.filter(page__snapshot=self, page__audited=True)
            .values("category_id", "title")
            .annotate(
                poor_count=Count("pk", filter=Q(rating=Rating.POOR)),
                needs_count=Count("pk", filter=Q(rating=Rating.NEEDS_IMPROVEMENT)),
                good_count=Count("pk", filter=Q(rating=Rating.GOOD)),
                score_avg=Avg("score"),
            )
        )

        SnapshotCategory.objects.filter(snapshot=self).delete()
        for row in cat_agg:
            SnapshotCategory.objects.create(
                snapshot=self,
                category_id=row["category_id"],
                title=row["title"],
                poor_count=row["poor_count"],
                needs_count=row["needs_count"],
                good_count=row["good_count"],
                score_avg=row["score_avg"],
            )

        # Aggregate audits
        audit_agg = (
            PageAudit.objects.filter(page__snapshot=self, page__audited=True)
            .values("audit_id")
            .annotate(
                poor_count=Count("pk", filter=Q(rating=Rating.POOR)),
                needs_count=Count("pk", filter=Q(rating=Rating.NEEDS_IMPROVEMENT)),
                good_count=Count("pk", filter=Q(rating=Rating.GOOD)),
            )
        )

        SnapshotAudit.objects.filter(snapshot=self).delete()
        for row in audit_agg:
            try:
                audit_def = AuditDefinition.objects.get(audit_id=row["audit_id"])
            except AuditDefinition.DoesNotExist:
                continue
            SnapshotAudit.objects.create(
                snapshot=self,
                audit=audit_def,
                poor_count=row["poor_count"],
                needs_count=row["needs_count"],
                good_count=row["good_count"],
            )

        self.page_count = pages_qs.count()
        self.status = Snapshot.Status.COMPLETE
        self.delete_config_file()
        self.save(update_fields=["page_count", "status"])
