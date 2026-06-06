import json
import logging
import os
import subprocess

from audits.models import Page, Report, Run
from django.conf import settings

log = logging.getLogger(__name__)


def generate_page_weights_report(run_pk: int, audit_pk: int, page_pk: int):

    page = Page.objects.get(pk=page_pk)
    run = Run.objects.get(pk=run_pk)
    extra = {"url": page.url}

    log.info("Page Weight audit started", extra=extra)

    report = Report(
        run_id=run_pk,
        page_id=page_pk,
        audit_id=audit_pk,
        data={}
    )

    try:
        script = os.path.join(settings.NODE_DIR, "src", "pageweight.js")

        result = subprocess.run(
            [script, page.url, f"--device={run.job.device}"],
            capture_output=True,
            timeout=120,
        )

        if result.returncode == 0:
            report.data = json.loads(result.stdout)
        else:
            report.error = result.stderr.decode(errors="replace")

    except Exception as exc:
        report.error = str(exc)

    report.save()

    if report.error:
        log.error("Page Weight audit failed", extra={**extra, "error": report.error})
    else:
        log.info("Page Weight audit passed", extra={**extra})
