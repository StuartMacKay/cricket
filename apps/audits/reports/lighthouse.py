import io
import json
import logging
import os
import subprocess
import tempfile

from audits.models import Audit, Definition, Finding, Metric, Page, Rating, Report, Run
from django.conf import settings
from django.core.files import File

log = logging.getLogger(__name__)


LIGHTHOUSE_SCRIPT = os.path.join(settings.NODE_DIR, "src", "lighthouse.js")


def generate_lighthouse_report(run_pk: int, audit_pk: int, page_pk: int):

    page = Page.objects.get(pk=page_pk)
    audit = Audit.objects.get(pk=audit_pk)
    run = Run.objects.get(pk=run_pk)
    extra = {"url": page.url}

    log.info("Lighthouse audit started", extra=extra)

    report = Report.objects.create(
        run_id=run_pk, page_id=page_pk, audit_id=audit_pk, data={}
    )

    config = {"formFactor": run.job.device, "onlyCategories": [f"{audit.slug}"]}

    lh_dir = os.path.join(
        tempfile.gettempdir(), f"lighthouse-run-{run_pk}-{page_pk}-{audit_pk}"
    )
    os.makedirs(lh_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", prefix=run.job.site.slug, suffix=".json", dir=lh_dir, delete=False
    ) as fp:
        json.dump(config, fp)
        config_file = fp.name

    html_fd, html_path = tempfile.mkstemp(suffix=".html", dir=lh_dir)
    os.close(html_fd)

    cli_flags = f"--cli-flags-path={config_file}"

    try:
        try:
            result = subprocess.run(
                [
                    LIGHTHOUSE_SCRIPT,
                    page.url,
                    "--quiet",
                    cli_flags,
                    f"--html-output-path={html_path}",
                ],
                capture_output=True,
                timeout=300,
            )

            if result.returncode == 0:
                report.json_report.save(
                    "lighthouse.json", File(io.BytesIO(result.stdout)), save=False
                )
                with open(html_path, "rb") as fp:
                    report.html_report.save("lighthouse.html", File(fp), save=False)

                data = json.loads(result.stdout)

                if "runtimeError" not in data and not data["runWarnings"]:
                    collect_metrics(report, run, data)
                    collect_findings(report, data)
                    log.info("Lighthouse audit passed", extra=extra)
                else:
                    report.error = "Lighthouse not audited (errors/warnings)"
                    log.info("Lighthouse audit failed", extra=extra)
            else:
                report.error = result.stderr
                log.error("Lighthouse audit failed", extra=extra)

        except Exception as exc:
            report.error = str(exc)

        report.save()

    finally:
        # TODO delete directory
        os.unlink(html_path)


# ------------------------------------------------------------------
# Metric extraction
# ------------------------------------------------------------------


def _save_metrics(report, run, data: dict, definitions: dict):
    """Create or update a Metric for each Definition that appears in the report.

    Iterates over known definitions rather than the raw report, so only metrics
    that have been explicitly registered are stored. Skips any definition whose
    slug is absent from the report or whose score is None (not applicable).

    Numeric values (value + units) are extracted only for definitions that carry
    a weight, i.e. the five Performance metrics that feed the overall score.
    """
    for slug, definition in definitions.items():
        lhr_audit = data["audits"].get(slug)
        if lhr_audit is None:
            continue

        raw_score = lhr_audit.get("score")
        if raw_score is None:
            continue

        score = int(raw_score * 100)
        rating = Rating.get_rating(score)

        if definition.weight:
            value = lhr_audit.get("numericValue")
            units = lhr_audit.get("numericUnit", "")
            if units == "millisecond" and value is not None:
                value = round(value)
            elif units == "unitless" and value is not None:
                value = round(value, 3)
        else:
            value, units = None, ""

        Metric.objects.update_or_create(
            report=report,
            definition=definition,
            defaults={
                "page_id": report.page_id,
                "measured": run.created,
                "score": score,
                "rating": rating,
                "value": value,
                "units": units,
            },
        )


def collect_metrics(report, run, data: dict):
    definitions = {
        d.slug: d
        for d in Definition.objects.filter(audit_id=report.audit_id)
    }
    if definitions:
        _save_metrics(report, run, data, definitions)


# ------------------------------------------------------------------
# Finding extraction
# ------------------------------------------------------------------

# Audit display modes that carry no actionable findings.
_SKIP_MODES = {"notApplicable", "error", "manual"}


def collect_findings(report, data: dict):
    """Extract one Finding per URL item from every failed Lighthouse audit.

    Iterates all audits in the report. Skips audits that are not applicable,
    errored, require manual review, or passed (score == 1). For every
    remaining audit that has items with a url field, creates a Finding.

    Severity is derived from the score: complete failures (score == 0) are
    warnings; partial failures are informational.
    """
    for slug, audit_data in data["audits"].items():
        if audit_data.get("scoreDisplayMode") in _SKIP_MODES:
            continue

        score = audit_data.get("score")
        if score is None or score == 1:
            continue

        severity = (
            Finding.Severity.WARNING if score == 0 else Finding.Severity.INFO
        )

        items = audit_data.get("details", {}).get("items", [])
        for item in items:
            url = item.get("url", "")
            if not url:
                continue

            Finding.objects.create(
                report=report,
                page=report.page,
                type=slug,
                url=url,
                title=audit_data.get("title", slug),
                description=audit_data.get("displayValue", ""),
                severity=severity,
                source="lighthouse",
                data=item,
            )
