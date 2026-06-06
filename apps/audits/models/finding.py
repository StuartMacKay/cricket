from django.db import models
from django.utils.translation import gettext_lazy as _


class Finding(models.Model):
    """An actionable item extracted from a Report.

    Findings represent specific issues that require attention — a dead link,
    a render-blocking resource, an oversized image. Unlike Metrics, Findings
    are open-ended: the type is a free slug (e.g. "dead-link", "large-image")
    rather than a pre-defined Definition. Findings can be created by the
    application's audit tasks or uploaded via the API by external agents or
    secondary processing tools.
    """

    class Meta:
        verbose_name = _("Finding")
        verbose_name_plural = _("Findings")

    class Severity(models.TextChoices):
        ERROR = "error", _("Error")
        WARNING = "warning", _("Warning")
        INFO = "info", _("Info")

    page = models.ForeignKey(
        "Page",
        on_delete=models.CASCADE,
        related_name="findings",
        verbose_name=_("Page"),
        help_text=_("The Page this Finding relates to."),
    )

    report = models.ForeignKey(
        "Report",
        on_delete=models.CASCADE,
        related_name="findings",
        verbose_name=_("Report"),
        help_text=_("The Report this Finding was extracted from."),
    )

    type = models.SlugField(
        max_length=100,
        db_index=True,
        verbose_name=_("Type"),
        help_text=_("A slug identifying the category of finding, e.g. 'dead-link', 'large-image'."),
    )

    title = models.CharField(
        max_length=255,
        verbose_name=_("Title"),
        help_text=_("A short description of the finding."),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Additional detail about the finding."),
    )

    url = models.URLField(
        blank=True,
        max_length=2000,
        verbose_name=_("URL"),
        help_text=_("The specific resource or URL this finding refers to, if applicable."),
    )

    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.WARNING,
        verbose_name=_("Severity"),
        help_text=_("The severity of the finding."),
    )

    source = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Source"),
        help_text=_("The tool or agent that generated this finding."),
    )

    data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Data"),
        help_text=_("Additional structured data for this finding."),
    )

    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("The date and time the record was added."),
    )

    def __str__(self):
        return f"{self.type}: {self.title}"
