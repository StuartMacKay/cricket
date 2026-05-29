from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class HeaderSnapshot(TimeStampedModel, models.Model):
    """A complete set of header audits for one site at one point in time."""

    class Meta:
        verbose_name = _("Header Snapshot")
        verbose_name_plural = _("Header Snapshots")
        ordering = ["-created"]

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED = "failed", _("Failed")

    site = models.ForeignKey(
        "lighthouse.Site",
        on_delete=models.CASCADE,
        related_name="header_snapshots",
        verbose_name=_("Site"),
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Status"),
        db_index=True,
    )

    page_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Page count"),
    )

    def __str__(self):
        return f"{self.site.name} ({self.created.strftime('%Y-%m-%d')})"
