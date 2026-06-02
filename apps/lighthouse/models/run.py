import pathlib

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel


class Run(TimeStampedModel, models.Model):
    class Meta:
        verbose_name = _("Run")
        verbose_name_plural = _("Runs")
        ordering = ["-created"]

    class Status(models.TextChoices):
        PENDING  = "pending",  _("Pending")
        RUNNING  = "running",  _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED   = "failed",   _("Failed")

    job = models.ForeignKey(
        "lighthouse.Job",
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name=_("Job"),
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name=_("Status"),
    )

    page_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Page count"),
        help_text=_("Populated on completion."),
    )

    # Temporary path to the Lighthouse config JSON; cleared after audits finish.
    config_file = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Config file"),
    )

    def __str__(self):
        return f"{self.job.site.name} ({self.created.strftime('%Y-%m-%d')})"

    def delete_config_file(self):
        if self.config_file:
            path = pathlib.Path(self.config_file)
            if path.exists() and path.is_file():
                path.unlink()
            self.config_file = ""
            self.save(update_fields=["config_file"])

    def complete(self):
        """Mark this Run complete and record the timestamp on the Job."""
        self.page_count = self.pages.count()
        self.status = Run.Status.COMPLETE
        self.delete_config_file()
        self.save(update_fields=["page_count", "status"])
        self.job.last_run = timezone.now()
        self.job.save(update_fields=["last_run"])
