import datetime as dt
import json
import logging
import os
import tempfile
import zlib
from typing import List, Union

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
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
    return os.path.join("sitemaps", instance.slug, filename)


class SiteQuerySet(models.QuerySet):
    def disabled(self) -> "SiteQuerySet":
        return self.filter(enabled=False)

    def enabled(self) -> "SiteQuerySet":
        return self.filter(enabled=True)

    def with_schedule(self) -> "SiteQuerySet":
        return self.exclude(crontab__exact="")


class SiteManager(models.Manager):
    def get_queryset(self):
        return SiteQuerySet(self.model, using=self._db)

    def overdue(self) -> List["Site"]:
        sites: List["Site"] = []
        timestamp = timezone.now()

        for site in self.all().enabled().with_schedule():
            if site.snapped is None:
                sites.append(site)
                continue

            cron = croniter(site.crontab, site.snapped)
            if cron.get_next(dt.datetime) < timestamp:
                sites.append(site)

        return sites


class Site(TimeStampedModel, models.Model):
    """A Site represents a web site to be audited with Lighthouse."""

    class Meta:
        verbose_name = _("Site")
        verbose_name_plural = _("Sites")

    class Platform(models.TextChoices):
        MOBILE = "mobile", _("Mobile")
        DESKTOP = "desktop", _("Desktop")

    name = models.CharField(
        verbose_name=_("Name"),
        help_text=_("The name of the site"),
        max_length=100,
    )

    slug = models.SlugField(
        verbose_name=_("Slug"),
        help_text=_("The slug uniquely identifying the Site"),
        max_length=100,
        unique=True,
    )

    url = models.URLField(
        verbose_name=_("URL"),
        help_text=_("The site's homepage"),
    )

    description = models.TextField(
        verbose_name=_("Description"),
        help_text=_("A description of the Site"),
        blank=True,
    )

    sitemap_url = models.URLField(
        verbose_name=_("Sitemap URL"),
        help_text=_("The URL to the site's sitemap"),
        blank=True,
    )

    sitemap_file = models.FileField(
        verbose_name=_("Sitemap file"),
        help_text=_("A file containing the sitemap for the Site"),
        upload_to=sitemap_path,
        null=True,
        blank=True,
    )

    platform = models.CharField(
        verbose_name=_("Platform"),
        help_text=_("The device form factor Lighthouse uses when auditing this site"),
        max_length=10,
        choices=Platform.choices,
        default=Platform.MOBILE,
    )

    extra_config = models.JSONField(
        verbose_name=_("Extra config"),
        help_text=_(
            "Additional Lighthouse config options (JSON). "
            "The Platform field above is always applied automatically; "
            "use this only for advanced overrides."
        ),
        default=dict,
        blank=True,
    )

    crontab = models.CharField(
        validators=[validate_crontab],
        verbose_name=_("Crontab"),
        help_text=_("Crontab entry which defines the time a Snapshot will be taken"),
        max_length=100,
        blank=True,
    )

    snapped = models.DateTimeField(
        verbose_name=_("Snapped"),
        help_text=_("The date and time the last Snapshot was taken"),
        null=True,
        blank=True,
    )

    enabled = models.BooleanField(
        verbose_name=_("Enabled"),
        help_text=_("Is the site active"),
    )

    current_snapshot = models.ForeignKey(
        "Snapshot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Current snapshot"),
        help_text=_("The most recently completed Snapshot for this site"),
    )

    objects = SiteManager()

    def __str__(self):
        return self.name

    def save(self, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(**kwargs)

    @staticmethod
    def _get_file(path: str) -> bytes:
        log.info("Sitemap from file", extra={"path": path})
        with open(path, "rb") as fp:
            return fp.read()

    @staticmethod
    def _get_url(url: HttpUrl) -> bytes:
        log.info("Sitemap from url", extra={"url": url})
        try:
            response = requests.get(url)
            if response.status_code >= 500:
                raise requests.exceptions.HTTPError(response=response)
            elif response.status_code >= 400:
                raise requests.exceptions.HTTPError(response=response)

            log.info(
                "Sitemap fetched", extra={"url": url, "status": response.status_code}
            )
            contents = response.content

            if contents[0:2] == bytes([0x1F, 0x8B]):
                log.info("Sitemap is compressed", extra={"url": url})
                contents = zlib.decompress(contents, 16 + zlib.MAX_WBITS)

        except requests.RequestException as err:
            extra = {"url": url}
            if err.response:
                extra["status_code"] = err.response.status_code
            log.exception("Sitemap not fetched", extra=extra)
            contents = b""

        return contents

    @staticmethod
    def _get_xml(contents: bytes):
        try:
            xml = etree.fromstring(contents)
        except etree.XMLSyntaxError:
            xml = None
        return xml

    def _load_sitemap(self, url: Union[HttpUrl, str]) -> List[HttpUrl]:
        if isinstance(url, str):
            contents = self._get_file(url)
        else:
            contents = self._get_url(url)

        if (root := self._get_xml(contents)) is None:
            log.exception("Sitemap not parsed", extra={"url": url})
            return []

        log.info("Sitemap parsed", extra={"url": url})

        if root.tag.endswith("sitemapindex"):
            log.info("Sitemap is index", extra={"url": url})
            for sitemap in root.getchildren():
                for loc in sitemap.iter("{*}loc"):
                    yield from self._load_sitemap(HttpUrl(loc.text))
        elif root.tag.endswith("urlset"):
            log.info("Sitemap is urlset", extra={"url": url})
            for element in root.getchildren():
                for loc in element.iter("{*}loc"):
                    url = HttpUrl(loc.text.strip())
                    log.info("Sitemap contains url", extra={"url": url})
                    yield url

    def get_urls(self) -> List[HttpUrl]:
        url = HttpUrl(self.sitemap_url) if self.sitemap_url else ""
        yield from self._load_sitemap(url or self.sitemap_file.path)

    def create_config_file(self) -> str:
        """Write a Lighthouse config JSON file and return its path.

        Merges extra_config with the platform's formFactor setting, with
        extra_config taking precedence for any other keys.
        """
        config = {**self.extra_config, "formFactor": self.platform}
        tmpdir = tempfile.gettempdir()
        lh_dir = os.path.join(tmpdir, "lighthouse-snapshot")
        if not os.path.exists(lh_dir):
            os.makedirs(lh_dir)
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix=self.slug,
            suffix=".json",
            dir=lh_dir,
            delete=False,
        ) as fp:
            json.dump(config, fp)
            return fp.name

    def create_snapshot(self) -> "Snapshot":
        from .snapshot import Snapshot

        snapshot = Snapshot.objects.create(
            site=self,
            status=Snapshot.Status.PENDING,
            platform=self.platform,
            config_file=self.create_config_file(),
        )
        self.snapped = timezone.now()
        self.save(update_fields=["snapped"])

        return snapshot
