import datetime
import logging
import os
import zlib

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

import requests
from croniter import croniter
from django_extensions.db.models import TimeStampedModel
from lxml import etree
from pydantic import HttpUrl

log = logging.getLogger(__name__)


def validate_crontab(value):
    if not croniter.is_valid(value):
        raise ValidationError(
            _('"%(value)s" is not a valid crontab entry'),
            params={"value": value},
        )


def sitemap_path(instance, filename):
    return os.path.join("sitemaps", instance.site.slug, filename)


class BaseJob(TimeStampedModel, models.Model):
    """Abstract base for all per-tool Job models.

    Each tool subclass adds its own typed configuration fields and sets
    TASK_NAME to the fully-qualified Celery task that creates a Run.

    URL discovery is handled here: url_source selects the input method and
    url_value / sitemap_file hold the data. get_urls() yields pydantic
    HttpUrl objects consumed by the collection task.
    """

    TASK_NAME: str | None = None  # e.g. 'lighthouse.tasks.take_lighthouse_run'

    class Meta:
        abstract = True

    class UrlSource(models.TextChoices):
        SITEMAP_URL  = "sitemap_url",  _("Sitemap URL")
        SITEMAP_FILE = "sitemap_file", _("Sitemap file")
        URL_LIST     = "url_list",     _("URL list")

    site = models.ForeignKey(
        "sites.Site",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_jobs",
        verbose_name=_("Site"),
    )

    url_source = models.CharField(
        max_length=20,
        choices=UrlSource.choices,
        default=UrlSource.SITEMAP_URL,
        verbose_name=_("URL source"),
    )

    url_value = models.TextField(
        blank=True,
        verbose_name=_("URL value"),
        help_text=_(
            "Sitemap URL, or newline-separated list of URLs when source is "
            '"URL list". Leave blank when using an uploaded sitemap file.'
        ),
    )

    sitemap_file = models.FileField(
        upload_to=sitemap_path,
        null=True,
        blank=True,
        verbose_name=_("Sitemap file"),
        help_text=_("Uploaded sitemap XML. Only used when source is 'Sitemap file'."),
    )

    environment = models.CharField(
        max_length=20,
        blank=True,
        choices=[
            ("local",      _("Local")),
            ("staging",    _("Staging")),
            ("production", _("Production")),
        ],
        verbose_name=_("Environment"),
        help_text=_("Where this Job runs — tags all Runs for filtering."),
    )

    crontab = models.CharField(
        max_length=100,
        blank=True,
        validators=[validate_crontab],
        verbose_name=_("Crontab"),
        help_text=_('Cron schedule, e.g. "0 9 * * 1" for Monday at 09:00. '
                    "Leave blank for manual-only Jobs."),
    )

    enabled = models.BooleanField(default=True, verbose_name=_("Enabled"))

    last_run = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last run"),
        help_text=_("Updated automatically when a Run is created."),
    )

    def __str__(self):
        return f"{self.site.name} — {self._meta.app_label}"

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def is_overdue(self, now=None):
        """True if this Job has a crontab and is due to run."""
        if not self.crontab:
            return False
        if self.last_run is None:
            return True
        if now is None:
            from django.utils import timezone
            now = timezone.now()
        cron = croniter(self.crontab, self.last_run)
        return cron.get_next(datetime.datetime) <= now

    def trigger_run(self):
        """Dispatch a new Run via Celery using TASK_NAME."""
        if not self.TASK_NAME:
            raise NotImplementedError(f"{self.__class__.__name__} must define TASK_NAME")
        from celery import current_app
        current_app.send_task(self.TASK_NAME, args=[self.pk])

    # ------------------------------------------------------------------
    # URL discovery
    # ------------------------------------------------------------------

    def get_urls(self):
        """Yield HttpUrl objects for every URL this Job should audit."""
        if self.url_source == self.UrlSource.URL_LIST:
            yield from self._urls_from_list()
        elif self.url_source == self.UrlSource.SITEMAP_FILE:
            if self.sitemap_file:
                contents = self._read_file(self.sitemap_file.path)
                yield from self._parse_sitemap(contents, source=str(self.sitemap_file))
        else:
            if self.url_value:
                contents = self._fetch_url(self.url_value)
                yield from self._parse_sitemap(contents, source=self.url_value)

    def _urls_from_list(self):
        for line in self.url_value.splitlines():
            url = line.strip()
            if url:
                yield HttpUrl(url)

    @staticmethod
    def _read_file(path):
        log.info("Sitemap from file", extra={"path": path})
        with open(path, "rb") as fp:
            return fp.read()

    @staticmethod
    def _fetch_url(url):
        log.info("Sitemap from url", extra={"url": url})
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            contents = response.content
            if contents[:2] == bytes([0x1F, 0x8B]):
                contents = zlib.decompress(contents, 16 + zlib.MAX_WBITS)
            log.info("Sitemap fetched", extra={"url": url})
            return contents
        except requests.RequestException:
            log.exception("Sitemap not fetched", extra={"url": url})
            return b""

    def _parse_sitemap(self, contents, source):
        try:
            xml = etree.fromstring(contents)
        except etree.XMLSyntaxError:
            log.exception("Sitemap not parsed", extra={"source": source})
            return
        if xml.tag.endswith("sitemapindex"):
            for sitemap in xml.getchildren():
                for loc in sitemap.iter("{*}loc"):
                    nested = loc.text.strip()
                    yield from self._parse_sitemap(self._fetch_url(nested), source=nested)
        elif xml.tag.endswith("urlset"):
            for element in xml.getchildren():
                for loc in element.iter("{*}loc"):
                    yield HttpUrl(loc.text.strip())
