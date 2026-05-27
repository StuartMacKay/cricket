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
        audits: dict[str, dict] = {}

        for key, audit in data["audits"].items():
            audits[key] = {
                "id": audit["id"],
                "title": audit["title"],
            }

        for key, category in data["categories"].items():
            for ref in category["auditRefs"]:
                audit = audits[ref["id"]]
                audit["category"] = key
                audit["weight"] = ref.get("weight", 0)
                audit["type"] = "numeric" if key == "performance" else "binary"

        for key, audit in data["audits"].items():
            if (score := audit["score"]) is None:
                audits[key]["type"] = None
                audits[key]["score"] = 0
                audits[key]["rating"] = 0
            else:
                if audits[key]["type"] == "numeric":
                    value = audit.get("numericValue")
                    units = audit.get("numericUnit")

                    if units == "millisecond":
                        value = round(value)
                    elif units == "unitless":
                        value = round(value, 3)

                    score = int(score * 100)
                    audits[key]["score"] = score
                    audits[key]["value"] = value
                    audits[key]["units"] = units
                    audits[key]["quantile"] = 19 if score == 100 else int(score / 5)
                    audits[key]["rating"] = Rating.get_rating(score)
                else:
                    audits[key]["score"] = score
                    audits[key]["rating"] = Rating.get_rating(score)

        self.data["audits"] = audits

    def _collect_category_metrics(self, data: dict):
        metrics: dict[str, dict] = {}
        for key, category in data["categories"].items():
            score = int(category["score"] * 100)
            metrics[key] = {
                "id": category["id"],
                "title": category["title"],
                "type": "numeric",
                "score": score,
                "rating": Rating.get_rating(score),
                "quantile": 19 if score == 100 else int(score / 5),
                "audits": [audit["id"] for audit in category["auditRefs"]],
            }
        self.data["categories"] = metrics

    def collect_metrics(self, data):
        self._collect_category_metrics(data)
        self._collect_audit_metrics(data)
        self.save()

    def audit(self):
        extra = {"url": self.url}
        log.info("Page audit started", extra=extra)

        result = subprocess.run(
            [
                LIGHTHOUSE_SCRIPT,
                self.url,
                "--quiet",
                "--cli-flags-path=%s" % self.snapshot.data["config_file"],
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
