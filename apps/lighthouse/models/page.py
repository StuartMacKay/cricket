import io
import json
import logging
import os
import subprocess
import tempfile

from django.conf import settings
from django.core.files import File
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel

from .rating import Rating

log = logging.getLogger(__name__)

LIGHTHOUSE_SCRIPT = os.path.join(settings.NODE_DIR, "src", "lighthouse.js")


def audit_report_path(instance, filename):
    slug = instance.snapshot.snapshot.site.slug
    name, extension = os.path.splitext(os.path.basename(filename))
    year = "%d" % instance.created.year
    month = "%02d" % instance.created.month
    day = "%02d" % instance.created.day
    hour = "%02d" % instance.created.hour
    name = "{}-{}{}".format(name, instance.pk, extension)
    return os.path.join("audit", slug, year, month, day, hour, name)


class Page(TimeStampedModel, models.Model):
    """A Page contains the Lighthouse audit results for a single web page URL."""

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")

    url = models.URLField(
        verbose_name=_("URL"),
        help_text=_("The URL of the page from the Site"),
    )

    report = models.FileField(
        upload_to=audit_report_path,
        verbose_name=_("Report"),
        help_text=_("The raw Lighthouse JSON report; pruned after 90 days"),
        null=True,
        blank=True,
    )

    html_report = models.FileField(
        upload_to=audit_report_path,
        verbose_name=_("HTML Report"),
        help_text=_(
            "The self-contained Lighthouse HTML report, "
            "identical to Chrome's Lighthouse panel output"
        ),
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

    def _upsert_audit_definitions(self, data: dict) -> dict[str, "AuditDefinition"]:
        """Upsert AuditDefinition rows and return a mapping of audit_id → definition."""
        from .audit import AuditDefinition

        # Build a mapping of audit_id → primary category and weight
        audit_meta: dict[str, dict] = {}
        for key, audit in data["audits"].items():
            audit_meta[key] = {
                "title": audit.get("title", key),
                "description": audit.get("description", ""),
            }

        for key, category in data["categories"].items():
            for ref in category.get("auditRefs", []):
                aid = ref["id"]
                if aid in audit_meta and "category_id" not in audit_meta[aid]:
                    audit_meta[aid]["category_id"] = key
                    audit_meta[aid]["weight"] = ref.get("weight", 0)

        definitions: dict[str, AuditDefinition] = {}
        for audit_id, meta in audit_meta.items():
            if "category_id" not in meta:
                continue  # Skip audits not mapped to a category
            obj, _ = AuditDefinition.objects.update_or_create(
                audit_id=audit_id,
                defaults={
                    "category_id": meta["category_id"],
                    "title": meta["title"],
                    "description": meta.get("description", ""),
                    "weight": meta.get("weight", 0),
                },
            )
            definitions[audit_id] = obj

        return definitions

    def _save_page_categories(self, data: dict):
        from .audit import PageCategory

        PageCategory.objects.filter(page=self).delete()
        for key, category in data["categories"].items():
            if category.get("score") is None:
                continue
            score = int(category["score"] * 100)
            rating = Rating.get_rating(score)
            if rating is None:
                continue
            PageCategory.objects.create(
                page=self,
                category_id=key,
                title=category.get("title", key),
                score=score,
                rating=rating,
            )

    def _save_page_audits(self, data: dict, definitions: dict):
        from .audit import PageAudit

        PageAudit.objects.filter(page=self).delete()

        for key, category in data["categories"].items():
            for ref in category.get("auditRefs", []):
                audit_id = ref["id"]
                audit_def = definitions.get(audit_id)
                if audit_def is None:
                    continue
                lhr_audit = data["audits"].get(audit_id, {})
                raw_score = lhr_audit.get("score")

                if raw_score is None:
                    score = None
                    rating = None
                    value = None
                    units = ""
                elif key == "performance" and ref.get("weight", 0) > 0:
                    # Numeric audit
                    score = int(raw_score * 100)
                    rating = Rating.get_rating(score)
                    value = lhr_audit.get("numericValue")
                    units = lhr_audit.get("numericUnit", "")
                    if units == "millisecond" and value is not None:
                        value = round(value)
                    elif units == "unitless" and value is not None:
                        value = round(value, 3)
                else:
                    # Binary audit (pass/fail)
                    score = int(raw_score * 100)
                    rating = Rating.get_rating(score)
                    value = None
                    units = ""

                # Avoid creating duplicates when an audit appears in multiple categories
                if PageAudit.objects.filter(page=self, audit=audit_def).exists():
                    continue

                PageAudit.objects.create(
                    page=self,
                    audit=audit_def,
                    score=score,
                    rating=rating,
                    value=value,
                    units=units,
                )

    def collect_metrics(self, data: dict):
        """Populate PageCategory and PageAudit from a Lighthouse report dict."""
        definitions = self._upsert_audit_definitions(data)
        self._save_page_categories(data)
        self._save_page_audits(data, definitions)

    def audit(self):
        extra = {"url": self.url}
        log.info("Page audit started", extra=extra)

        html_fd, html_path = tempfile.mkstemp(suffix=".html")
        os.close(html_fd)

        try:
            try:
                result = subprocess.run(
                    [
                        LIGHTHOUSE_SCRIPT,
                        self.url,
                        "--quiet",
                        "--cli-flags-path=%s" % self.snapshot.config_file,
                        "--html-output-path=%s" % html_path,
                    ],
                    capture_output=True,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                log.error("Page audit timed out", extra=extra)
                fp = io.BytesIO(b"Audit timed out after 300 seconds")
                self.report.save("lighthouse.txt", File(fp), save=False)
                self.audited = False
                self.save()
                return

            if result.returncode == 0:
                fp = io.BytesIO(result.stdout)
                self.report.save("lighthouse.json", File(fp), save=False)

                with open(html_path, "rb") as html_fp:
                    self.html_report.save("lighthouse.html", File(html_fp), save=False)

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
        finally:
            os.unlink(html_path)
