import logging

import requests
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel

log = logging.getLogger(__name__)

TIMEOUT = 30  # seconds


class Page(TimeStampedModel, models.Model):
    """HTTP response headers collected for a single URL."""

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        ordering = ["url"]
        indexes = [
            models.Index(fields=["snapshot", "url"]),
        ]

    snapshot = models.ForeignKey(
        "Snapshot",
        on_delete=models.CASCADE,
        related_name="pages",
        verbose_name=_("Snapshot"),
    )

    url = models.URLField(
        verbose_name=_("URL"),
        max_length=2000,
    )

    final_url = models.URLField(
        verbose_name=_("Final URL"),
        max_length=2000,
        blank=True,
        help_text=_("URL after following redirects; same as url if no redirect"),
    )

    status_code = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Status code"),
    )

    redirect_count = models.IntegerField(
        default=0,
        verbose_name=_("Redirect count"),
    )

    headers = models.JSONField(
        default=dict,
        verbose_name=_("Headers"),
        help_text=_("Response headers from the final URL, keys lowercased"),
    )

    error = models.TextField(
        blank=True,
        verbose_name=_("Error"),
        help_text=_("Network or timeout error, if any"),
    )

    def fetch(self):
        """Fetch the URL and record the response headers."""
        extra = {"url": self.url}
        log.info("Fetching headers", extra=extra)
        try:
            response = requests.get(
                self.url,
                timeout=TIMEOUT,
                allow_redirects=True,
                headers={"User-Agent": "cricket/1.0 headers-audit"},
            )
            self.redirect_count = len(response.history)
            self.final_url = str(response.url)
            self.status_code = response.status_code
            self.headers = dict(response.headers.lower_items())
            log.info("Headers fetched", extra={**extra, "status": self.status_code})
        except requests.Timeout:
            self.error = f"Timeout after {TIMEOUT}s"
            log.warning("Header fetch timed out", extra=extra)
        except requests.RequestException as exc:
            self.error = str(exc)
            log.warning("Header fetch failed", extra={**extra, "error": str(exc)})
        self.save()

    def __str__(self):
        return self.url
