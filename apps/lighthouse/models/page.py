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
    slug = instance.run.job.site.slug
    name, extension = os.path.splitext(os.path.basename(filename))
    year  = "%d"  % instance.created.year
    month = "%02d" % instance.created.month
    day   = "%02d" % instance.created.day
    hour  = "%02d" % instance.created.hour
    name  = f"{name}-{instance.pk}{extension}"
    return os.path.join("audit", slug, year, month, day, hour, name)


class Page(TimeStampedModel, models.Model):
    """Lighthouse audit results for a single URL in a Run."""

    class Meta:
        verbose_name = _("Page")
        verbose_name_plural = _("Pages")
        unique_together = [("run", "url")]

    run = models.ForeignKey(
        "Run",
        on_delete=models.CASCADE,
        related_name="pages",
        verbose_name=_("Run"),
    )

    url = models.URLField(max_length=2000, verbose_name=_("URL"))

    report = models.FileField(
        upload_to=audit_report_path,
        null=True, blank=True,
        verbose_name=_("Report"),
        help_text=_("Raw Lighthouse JSON report; pruned after 90 days."),
    )

    html_report = models.FileField(
        upload_to=audit_report_path,
        null=True, blank=True,
        verbose_name=_("HTML Report"),
        help_text=_("Self-contained Lighthouse HTML report."),
    )

    audited = models.BooleanField(
        default=False,
        verbose_name=_("Audited"),
        help_text=_("True when the audit completed without errors or warnings."),
    )

    def __str__(self):
        return self.url

    def read_report(self) -> dict:
        with self.report.open() as fp:
            return json.load(fp)

    # ------------------------------------------------------------------
    # Metric extraction
    # ------------------------------------------------------------------

    def _upsert_audit_definitions(self, data: dict) -> dict:
        from .audit import AuditDefinition
        from lighthouse.audit_ids import stable_audit_id

        audit_meta: dict[str, dict] = {}
        for key, audit in data["audits"].items():
            audit_meta[key] = {
                "title":       audit.get("title", key),
                "description": audit.get("description", ""),
            }

        for key, category in data["categories"].items():
            for ref in category.get("auditRefs", []):
                aid = ref["id"]
                if aid in audit_meta and "category_id" not in audit_meta[aid]:
                    audit_meta[aid]["category_id"] = key
                    audit_meta[aid]["weight"]      = ref.get("weight", 0)

        definitions = {}
        for audit_id, meta in audit_meta.items():
            if "category_id" not in meta:
                continue
            cricket_id = stable_audit_id(audit_id)
            obj, _ = AuditDefinition.objects.update_or_create(
                audit_id=cricket_id,
                defaults={
                    "category_id": meta["category_id"],
                    "title":       meta["title"],
                    "description": meta.get("description", ""),
                    "weight":      meta.get("weight", 0),
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
            score  = int(category["score"] * 100)
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
                audit_id  = ref["id"]
                audit_def = definitions.get(audit_id)
                if audit_def is None:
                    continue
                lhr_audit = data["audits"].get(audit_id, {})
                raw_score = lhr_audit.get("score")

                if raw_score is None:
                    score, rating, value, units = None, None, None, ""
                elif key == "performance" and ref.get("weight", 0) > 0:
                    score  = int(raw_score * 100)
                    rating = Rating.get_rating(score)
                    value  = lhr_audit.get("numericValue")
                    units  = lhr_audit.get("numericUnit", "")
                    if units == "millisecond" and value is not None:
                        value = round(value)
                    elif units == "unitless" and value is not None:
                        value = round(value, 3)
                else:
                    score  = int(raw_score * 100)
                    rating = Rating.get_rating(score)
                    value, units = None, ""

                if PageAudit.objects.filter(page=self, audit=audit_def).exists():
                    continue

                PageAudit.objects.create(
                    page=self, audit=audit_def,
                    score=score, rating=rating,
                    value=value, units=units,
                )

    def collect_metrics(self, data: dict):
        definitions = self._upsert_audit_definitions(data)
        self._save_page_categories(data)
        self._save_page_audits(data, definitions)

    # ------------------------------------------------------------------
    # Lighthouse subprocess
    # ------------------------------------------------------------------

    def audit(self):
        extra = {"url": self.url}
        log.info("Page audit started", extra=extra)

        html_fd, html_path = tempfile.mkstemp(suffix=".html")
        os.close(html_fd)

        cli_flags = f"--cli-flags-path={self.run.config_file}"

        try:
            try:
                result = subprocess.run(
                    [LIGHTHOUSE_SCRIPT, self.url, "--quiet", cli_flags,
                     f"--html-output-path={html_path}"],
                    capture_output=True,
                    timeout=300,
                )
            except subprocess.TimeoutExpired:
                log.error("Page audit timed out", extra=extra)
                self.report.save("lighthouse.txt", File(io.BytesIO(b"Timed out after 300s")), save=False)
                self.audited = False
                self.save()
                return

            if result.returncode == 0:
                self.report.save("lighthouse.json", File(io.BytesIO(result.stdout)), save=False)
                with open(html_path, "rb") as fp:
                    self.html_report.save("lighthouse.html", File(fp), save=False)
                data = json.loads(result.stdout)
                if "runtimeError" not in data and not data["runWarnings"]:
                    self.collect_metrics(data)
                    self.audited = True
                    log.info("Page audited", extra=extra)
                else:
                    self.audited = False
                    log.info("Page not audited (errors/warnings)", extra=extra)
            else:
                self.report.save("lighthouse.txt", File(io.BytesIO(result.stderr)), save=False)
                self.audited = False
                log.error("Page audit failed", extra=extra)

            self.save()
        finally:
            os.unlink(html_path)
