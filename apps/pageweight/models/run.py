from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class Run(TimeStampedModel, models.Model):
    """A complete set of page weight measurements for one site at one point in time."""

    class Meta:
        verbose_name = _("Run")
        verbose_name_plural = _("Runs")
        ordering = ["-created"]

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED = "failed", _("Failed")

    scan = models.ForeignKey(
        "sites.Scan",
        on_delete=models.CASCADE,
        related_name="pageweight_run",
        verbose_name=_("Scan"),
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
        return f"{self.scan.site.name} ({self.created.strftime('%Y-%m-%d')})"
