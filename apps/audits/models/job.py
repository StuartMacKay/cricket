import datetime
import logging
import os
import requests
import zlib
from urllib.parse import urlparse
from croniter import croniter
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from lxml import etree
from pydantic import HttpUrl

log = logging.getLogger(__name__)


def validate_crontab(value):
    if not croniter.is_valid(value):
        raise ValidationError(
            _('"%(value)s" is not a valid crontab entry'),
            params={"value": value},
        )


class JobQuerySet(models.QuerySet):

    def active(self):
        return self.filter(enabled=True)

    def scheduled(self):
        return self.exclude(schedule="")


class JobManager(models.Manager):

    def get_queryset(self):
        return JobQuerySet(self.model, using=self._db)

    def overdue(self) -> list("Job"):
        results = []
        now = timezone.now()
        for job in self.get_queryset().active().scheduled():
            if job.is_overdue(now):
                results.append(job)
        return results


class Job(models.Model):
    """Configuration for an audit run: which site, which audits, which pages, and when.

    A Job selects a Site, a set of Audits to run, and the pages to audit —
    either discovered from sitemaps or supplied as an explicit URL list.
    Jobs can be triggered manually or run automatically on a cron schedule.
    Each execution creates a Run which tracks progress and links all Reports.
    """

    class Device(models.TextChoices):
        MOBILE  = "mobile",  _("Mobile")
        DESKTOP = "desktop", _("Desktop")

    class Meta:
        verbose_name = _("Job")
        verbose_name_plural = _("Jobs")

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name"),
        help_text=_("The name of the job.")
    )

    site = models.ForeignKey(
        "Site",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_jobs",
        verbose_name=_("Site"),
        help_text=_("The site to be audited.")
    )

    sitemaps = models.TextField(
        blank=True,
        verbose_name=_("Sitemaps"),
        help_text=_("Optional. A newline-separated list of sitemaps to load."),
    )

    urls = models.TextField(
        blank=True,
        verbose_name=_("URLs"),
        help_text=_("Optional. A newline-separated list of page URLs to audit."),
    )

    device = models.CharField(
        max_length=10,
        choices=Device.choices,
        default=Device.MOBILE,
        verbose_name=_("Device"),
        help_text=_("The device to emulate when running an audit.")
    )

    audits = models.ManyToManyField(
        "Audit",
        verbose_name=_("Audits"),
        help_text=_("The audits to perform on each page from the site.")
    )

    schedule = models.CharField(
        max_length=100,
        blank=True,
        validators=[validate_crontab],
        verbose_name=_("Schedule"),
        help_text=_(
            "Optional. A crontab schedule for running the job."
        ),
    )

    enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
        help_text=_("Is the job active?")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_(
            "A description of the job. Add any additional detail to "
            "distinguish between jobs for the same site."
        )
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

    executed = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last run"),
        help_text=_("The date and time this job was last executed. Updated automatically."),
    )

    objects = JobManager()

    def __str__(self):
        return f"{self.site} — {self.name}"

    def clean(self):
        if not self.site_id:
            return
        site_domain = urlparse(self.site.url).netloc
        errors = {}
        for field_name, text in [("sitemaps", self.sitemaps), ("urls", self.urls)]:
            bad = [
                url
                for line in text.splitlines()
                if (url := line.strip()) and urlparse(url).netloc != site_domain
            ]
            if bad:
                errors[field_name] = _(
                    "These URLs do not belong to %(domain)s: %(urls)s"
                ) % {"domain": site_domain, "urls": ", ".join(bad)}
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def is_overdue(self, now):
        """True if this Job has a crontab and is due to run."""
        if not self.schedule:
            return False
        if self.executed is None:
            return True
        cron = croniter(self.schedule, self.executed)
        return cron.get_next(datetime.datetime) <= now

    # ------------------------------------------------------------------
    # URL discovery
    # ------------------------------------------------------------------

    def get_urls(self):
        """Yield HttpUrl objects for every URL this Job should audit."""
        for line in self.sitemaps.splitlines():
            if sitemap_url := line.strip():
                sitemap = self._fetch_url(sitemap_url)
                yield from self._parse_sitemap(sitemap, sitemap_url)

        for line in self.urls.splitlines():
            if url := line.strip():
                yield HttpUrl(url)

    def get_pages(self):
        """Yield Page objects for every URL this Job should audit.

        Creates Page records that do not yet exist. Callers can assume all
        yielded pages are persisted and ready to reference from a Report.
        """
        from .page import Page

        for url in self.get_urls():
            page, _ = Page.objects.get_or_create(site=self.site, url=str(url))
            yield page

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
