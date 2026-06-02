import logging

import requests
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel

log = logging.getLogger(__name__)
TIMEOUT = 30


class Page(TimeStampedModel, models.Model):
    """HTTP response headers for a single URL in a Run."""

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        unique_together = [("run", "url")]

    run = models.ForeignKey(
        "headers.Run",
        on_delete=models.CASCADE,
        related_name="pages",
        verbose_name=_("Run"),
    )

    url            = models.URLField(max_length=2000, verbose_name=_("URL"))
    final_url      = models.URLField(max_length=2000, blank=True, verbose_name=_("Final URL"))
    status_code    = models.IntegerField(null=True, blank=True, verbose_name=_("Status code"))
    redirect_count = models.IntegerField(default=0, verbose_name=_("Redirect count"))
    headers        = models.JSONField(default=dict, verbose_name=_("Headers"))
    error          = models.TextField(blank=True, verbose_name=_("Error"))

    def __str__(self):
        return self.url

    def fetch(self):
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
            self.final_url      = str(response.url)
            self.status_code    = response.status_code
            self.headers        = dict(response.headers.lower_items())
            log.info("Headers fetched", extra={**extra, "status": self.status_code})
        except requests.Timeout:
            self.error = f"Timeout after {TIMEOUT}s"
            log.warning("Header fetch timed out", extra=extra)
        except requests.RequestException as exc:
            self.error = str(exc)
            log.warning("Header fetch failed", extra={**extra, "error": str(exc)})
        self.save()
