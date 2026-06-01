import pathlib

from django.db import models
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel


class Run(TimeStampedModel, models.Model):
    class Meta:
        verbose_name = _("Run")
        verbose_name_plural = _("Runs")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED = "failed", _("Failed")

    scan = models.ForeignKey(
        "sites.Scan",
        models.CASCADE,
        related_name="lighthouse_run",
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
        help_text=_("Total number of pages audited; populated when complete"),
    )

    # Temporary path to the Lighthouse config JSON file; cleared after audits finish.
    config_file = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Config file"),
        help_text=_("Temporary path to the Lighthouse config file"),
    )

    def __str__(self):
        return "{} ({})".format(self.scan.site.name, self.created.strftime("%Y-%m-%d"))

    def get_page_keys(self):
        return self.scan.pages.values_list("pk", flat=True)

    def get_number_of_pages(self) -> int:
        return int(self.scan.pages.count())

    def delete_config_file(self):
        if self.config_file:
            path = pathlib.Path(self.config_file)
            if path.exists() and path.is_file():
                path.unlink()
            self.config_file = ""
            self.save(update_fields=["config_file"])

    def complete(self):
        """Mark this run and its parent scan complete."""
        from sites.models import Scan, Site

        self.page_count = self.scan.pages.count()
        self.status = Run.Status.COMPLETE
        self.delete_config_file()
        self.save(update_fields=["page_count", "status"])

        self.scan.status = Scan.Status.COMPLETE
        self.scan.save(update_fields=["status"])
        Site.objects.filter(pk=self.scan.site_id).update(current_scan=self.scan)
