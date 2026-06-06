from django.db import models
from django.utils.translation import gettext_lazy as _


class Page(models.Model):
    """A URL belonging to a Site that has been, or will be, audited.

    Pages are created during Job execution as URLs are discovered from
    sitemaps or the Job's explicit URL list. The same Page record is reused
    across multiple Runs, so Reports from different Runs can be compared for
    the same URL.
    """

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")

    site = models.ForeignKey(
        "Site",
        on_delete=models.CASCADE,
        related_name="pages",
        verbose_name=_("Site"),
        help_text=_("The site for this page.")
    )

    url = models.URLField(
        max_length=2000,
        unique=True,
        verbose_name=_("URL"),
        help_text=_("The URL for the page")
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
        return self.url
