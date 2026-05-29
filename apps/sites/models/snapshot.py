from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class Snapshot(TimeStampedModel, models.Model):
    class Meta:
        verbose_name = _("Snapshot")
        verbose_name_plural = _("Snapshots")
        ordering = ["-created"]

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED = "failed", _("Failed")

    site = models.ForeignKey(
        "Site",
        on_delete=models.CASCADE,
        related_name="snapshots",
        verbose_name=_("Site"),
    )

    platform = models.CharField(
        max_length=10,
        verbose_name=_("Platform"),
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("Status"),
        db_index=True,
    )

    webhook_url = models.URLField(
        verbose_name=_("Webhook URL"),
        help_text=_("Optional URL to POST to when the snapshot completes"),
        blank=True,
    )

    def __str__(self):
        return f"{self.site.name} ({self.created.strftime('%Y-%m-%d')})"
