from django.db import models
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel


class Page(TimeStampedModel, models.Model):
    """A single URL included in a Scan. Shared across all tool result models."""

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        unique_together = [("scan", "url")]

    scan = models.ForeignKey(
        "Scan",
        on_delete=models.CASCADE,
        related_name="pages",
        verbose_name=_("Scan"),
    )

    url = models.URLField(
        max_length=2000,
        verbose_name=_("URL"),
    )

    def __str__(self):
        return self.url
