import io
import json
import logging
import os
import subprocess

from django.conf import settings
from django.core.files import File
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel

from .rating import Rating

log = logging.getLogger(__name__)

LIGHTHOUSE_SCRIPT = os.path.join(settings.NODE_DIR, "src", "lighthouse.js")


def audit_report_path(instance, filename):
    slug = instance.snapshot.site.slug
    name, extension = os.path.splitext(os.path.basename(filename))
    year = "%d" % instance.created.year
    month = "%02d" % instance.created.month
    day = "%02d" % instance.created.day
    hour = "%02d" % instance.created.hour
    name = "{}-{}{}".format(name, instance.pk, extension)
    return os.path.join("audit", slug, year, month, day, hour, name)


class Page(TimeStampedModel, models.Model):
    """
    A Page contains the analytics data for a web page.
    """

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")

    url = models.URLField(
        verbose_name=_("URL"),
        help_text=_("The URL of the page from the Site"),
    )

    data = models.JSONField(
        verbose_name=_("Data"),
        help_text=_("A summary of the audit data for this Page"),
        default=dict,
    )

    report = models.FileField(
        upload_to=audit_report_path,
        verbose_name=_("Report"),
        help_text=_("The Lighthouse audit report for this Page"),
        null=True,
        blank=True,
    )

    audited = models.BooleanField(
        verbose_name=_("Audited"),
        help_text=_(
            "The page was audited successfully, with no errors or warnings reported"
        ),
    )

    snapshot = models.ForeignKey(
        "Snapshot",
        models.CASCADE,
        related_name="pages",
        verbose_name=_("Snapshot"),
        help_text=_("The Snapshot that this Page belongs to"),
    )

    def __str__(self):
        return self.url

    def read_report(self) -> dict:
        with self.report.open() as fp:
            return json.load(fp)

    def _collect_audit_metrics(self, data: dict):
        metrics: dict[str, dict] = {}
        for key, audit in data.items():
            score = audit.get("score") or 0
            score = int(score * 100)

            if audit.get("numericUnit") == "millisecond":
                value = round(data[key]["numericValue"])
            elif audit.get("numericUnit") == "unitless":
                value = round(data[key]["numericValue"], 3)
            else:
                value = audit.get("numericValue")

            if audit["scoreDisplayMode"] == "binary":
                audit_type = "binary"
            else:
                audit_type = "numeric"

            metrics[key] = {
                "id": audit["id"],
                "title": audit["title"],
                "score": score,
                "rating": Rating.get_rating(score),
                "type": audit_type,
                "units": audit.get("numericUnit"),
                "value": value,
            }

        self.data["audits"] = metrics

    def _collect_category_metrics(self, data: dict):
        metrics: dict[str, dict[str, int]] = {}
        for key, category in data.items():
            score = int(category["score"] * 100)
            metrics[key] = {
                "id": category["id"],
                "title": category["title"],
                "score": score,
                "rating": Rating.get_rating(score),
                "audits": [audit["id"] for audit in category["auditRefs"]],
            }
        self.data["categories"] = metrics

    def collect_metrics(self, data):
        self._collect_category_metrics(data["categories"]),
        self._collect_audit_metrics(data["audits"]),
        self.save()

    def audit(self):
        extra = {"url": self.url}
        log.info("Page audit started", extra=extra)

        result = subprocess.run(
            [
                LIGHTHOUSE_SCRIPT,
                self.url,
                "--quiet",
                "--cli-flags-path=%s" % self.snapshot.site.config_file.path,
            ],
            capture_output=True,
        )

        if result.returncode == 0:
            fp = io.BytesIO(result.stdout)
            self.report.save("lighthouse.json", File(fp), save=False)

            data = json.loads(result.stdout)

            if "runtimeError" not in data and not data["runWarnings"]:
                self.collect_metrics(data)
                self.audited = True
                log.info("Page was audited", extra=extra)
            else:
                self.audited = False
                log.info("Page was not audited", extra=extra)
        else:
            fp = io.BytesIO(result.stderr)
            self.report.save("lighthouse.txt", File(fp), save=False)

            self.audited = False
            log.error("Page was not audited", extra=extra)

        self.save()
