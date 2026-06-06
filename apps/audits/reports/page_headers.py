import logging

import requests
from audits.models import Page, Report, Run

log = logging.getLogger(__name__)


def generate_page_header_report(run_pk: int, audit_pk: int, page_pk: int):

    page = Page.objects.get(pk=page_pk)
    extra = {"url": page.url}

    log.info("Page Header audit started", extra=extra)

    report = Report(
        run_id=run_pk,
        page_id=page_pk,
        audit_id=audit_pk,
        data={}
    )

    try:
        response = requests.get(
            page.url,
            timeout=30,
            allow_redirects=True,
            headers={"User-Agent": "cricket/1.0 headers-audit"},
        )

        report.data = {
            "redirect_count": len(response.history),
            "final_url": str(response.url),
            "status_code": response.status_code,
            "headers": dict(response.headers.items())
        }

    except Exception as exc:
        report.error = str(exc)

    report.save()

    if report.error:
        log.warning("Page Header audit failed", extra={**extra, "error": report.error})
    else:
        log.info("Page Headers fetched", extra={**extra, "status": response.status_code})
