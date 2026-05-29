import json
import logging
import os
import subprocess

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

log = logging.getLogger(__name__)

PAGEWEIGHT_SCRIPT = os.path.join(settings.NODE_DIR, "src", "pageweight.js")

RESOURCE_TYPES = ["document", "stylesheet", "script", "image", "font", "other"]


class PageWeight(TimeStampedModel, models.Model):
    """Page weight summary for a single URL.

    Stores total transfer and resource sizes plus a breakdown by resource type.
    Individual resources are stored in related PageResource rows.
    """

    class Meta:
        verbose_name = _("Page Weight")
        verbose_name_plural = _("Page Weights")
        ordering = ["-total_transfer_size"]
        indexes = [
            models.Index(fields=["snapshot", "url"]),
            models.Index(fields=["snapshot", "total_transfer_size"]),
        ]

    snapshot = models.ForeignKey(
        "WeightSnapshot",
        on_delete=models.CASCADE,
        related_name="pages",
        verbose_name=_("Snapshot"),
    )

    url = models.URLField(max_length=2000, verbose_name=_("URL"))
    final_url = models.URLField(max_length=2000, blank=True, verbose_name=_("Final URL"))

    measured = models.BooleanField(
        default=False,
        verbose_name=_("Measured"),
        help_text=_("True when Puppeteer completed without error"),
    )

    total_transfer_size = models.BigIntegerField(
        default=0,
        verbose_name=_("Total transfer size (bytes)"),
        help_text=_("Compressed bytes received over the network"),
    )

    total_resource_size = models.BigIntegerField(
        default=0,
        verbose_name=_("Total resource size (bytes)"),
        help_text=_("Uncompressed resource size in bytes"),
    )

    resource_count = models.IntegerField(default=0, verbose_name=_("Resource count"))

    # Per-type breakdown stored as integers (bytes)
    document_transfer = models.BigIntegerField(default=0)
    stylesheet_transfer = models.BigIntegerField(default=0)
    script_transfer = models.BigIntegerField(default=0)
    image_transfer = models.BigIntegerField(default=0)
    font_transfer = models.BigIntegerField(default=0)
    other_transfer = models.BigIntegerField(default=0)

    document_size = models.BigIntegerField(default=0)
    stylesheet_size = models.BigIntegerField(default=0)
    script_size = models.BigIntegerField(default=0)
    image_size = models.BigIntegerField(default=0)
    font_size = models.BigIntegerField(default=0)
    other_size = models.BigIntegerField(default=0)

    error = models.TextField(blank=True, verbose_name=_("Error"))

    def __str__(self):
        return self.url

    def measure(self):
        """Run the Puppeteer script and populate this row plus PageResource rows."""
        extra = {"url": self.url, "snapshot": self.snapshot_id}
        log.info("Page weight measurement started", extra=extra)

        platform = self.snapshot.platform
        try:
            result = subprocess.run(
                [PAGEWEIGHT_SCRIPT, self.url, f"--device={platform}"],
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            self.error = "Timed out after 120s"
            self.measured = False
            self.save()
            log.error("Page weight measurement timed out", extra=extra)
            return

        if result.returncode != 0:
            self.error = result.stderr.decode(errors="replace")
            self.measured = False
            self.save()
            log.error("Page weight measurement failed", extra={**extra, "error": self.error})
            return

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.error = f"JSON parse error: {exc}"
            self.measured = False
            self.save()
            return

        self.final_url = data.get("finalUrl", "")
        self.total_transfer_size = data.get("totalTransferSize", 0)
        self.total_resource_size = data.get("totalResourceSize", 0)
        self.resource_count = data.get("resourceCount", 0)
        self.measured = True

        by_type = data.get("byType", {})
        for rtype in RESOURCE_TYPES:
            entry = by_type.get(rtype, {})
            setattr(self, f"{rtype}_transfer", entry.get("transferSize", 0))
            setattr(self, f"{rtype}_size", entry.get("resourceSize", 0))

        self.save()

        # Persist individual resources
        PageResource.objects.filter(page=self).delete()
        resources = [
            PageResource(
                page=self,
                url=r["url"][:2000],
                resource_type=r.get("type", "other"),
                mime_type=r.get("mimeType", "")[:100],
                transfer_size=r.get("transferSize", 0),
                resource_size=r.get("resourceSize", 0),
            )
            for r in data.get("resources", [])
        ]
        PageResource.objects.bulk_create(resources, batch_size=500)
        log.info("Page weight measured", extra={**extra, "transfer": self.total_transfer_size})


class PageResource(models.Model):
    """A single network resource loaded by a page during the Puppeteer measurement."""

    class Meta:
        verbose_name = _("Page Resource")
        verbose_name_plural = _("Page Resources")
        indexes = [
            models.Index(fields=["page", "resource_type"]),
            models.Index(fields=["page", "transfer_size"]),
        ]

    page = models.ForeignKey(
        PageWeight,
        on_delete=models.CASCADE,
        related_name="resources",
        verbose_name=_("Page"),
    )

    url = models.URLField(max_length=2000, verbose_name=_("URL"))
    resource_type = models.CharField(max_length=20, verbose_name=_("Type"))
    mime_type = models.CharField(max_length=100, blank=True, verbose_name=_("MIME type"))
    transfer_size = models.BigIntegerField(default=0, verbose_name=_("Transfer size (bytes)"))
    resource_size = models.BigIntegerField(default=0, verbose_name=_("Resource size (bytes)"))

    def __str__(self):
        return f"{self.resource_type}: {self.url}"
