import os

from django.db import models
from django.utils.translation import gettext_lazy as _


def audit_report_path(instance, filename):
    slug = instance.page.site.slug
    name, extension = os.path.splitext(os.path.basename(filename))
    year = "%d" % instance.created.year
    month = "%02d" % instance.created.month
    day = "%02d" % instance.created.day
    hour = "%02d" % instance.created.hour
    name = f"{name}-{instance.pk}{extension}"
    return os.path.join("audit", slug, year, month, day, hour, name)


class Report(models.Model):
    """The raw output of running one Audit against one Page in a given Run.

    One Report is created per (Run, Audit, Page) combination. The raw tool
    output is stored in the data JSONField; the audit task populates this
    after performing the audit. Values are extracted from the Report by the
    audit task and stored as individual Value records for trend analysis.
    If the audit fails, the error field holds the exception detail and data
    remains empty.
    """

    class Meta:
        verbose_name = _("Report")
        verbose_name_plural = _("Reports")

    page = models.ForeignKey(
        "Page",
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name=_("Page"),
        help_text=_("The Page that was audited to generate this Report."),
    )

    audit = models.ForeignKey(
        "Audit",
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name=_("Audit"),
        help_text=_("The Audit that generated this Report."),
    )

    run = models.ForeignKey(
        "Run",
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name=_("Run"),
        help_text=_("The Run that generated this Report."),
    )

    json_report = models.FileField(
        upload_to=audit_report_path,
        null=True,
        blank=True,
        verbose_name=_("Report"),
        help_text=_("Audit results in JSON format."),
    )

    html_report = models.FileField(
        upload_to=audit_report_path,
        null=True,
        blank=True,
        verbose_name=_("HTML Report"),
        help_text=_("Audit results in HTML format."),
    )

    data = models.JSONField(
        default=dict,
        verbose_name=_("Data"),
        help_text=_("The raw data from running the audit."),
    )

    error = models.TextField(
        blank=True,
        verbose_name=_("Error"),
        help_text=_("A description, or stack trace for any errors."),
    )

    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("The date and time the record was added."),
    )

    modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified at"),
        help_text=_("The date and time the record was last modified."),
    )

    def __str__(self):
        return f"{self.audit} - {self.page}"
