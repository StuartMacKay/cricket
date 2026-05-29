from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class WeightSnapshot(TimeStampedModel, models.Model):
    """A complete set of page weight measurements for one site at one point in time."""

    class Meta:
        verbose_name = _("Weight Snapshot")
        verbose_name_plural = _("Weight Snapshots")
        ordering = ["-created"]

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED = "failed", _("Failed")

    site = models.ForeignKey(
        "lighthouse.Site",
        on_delete=models.CASCADE,
        related_name="weight_snapshots",
        verbose_name=_("Site"),
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
        help_text=_("'mobile' or 'desktop'"),
    )

    page_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Page count"),
    )

    def __str__(self):
        return f"{self.site.name} ({self.created.strftime('%Y-%m-%d')}) [{self.platform}]"
