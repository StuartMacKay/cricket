from typing import Annotated, Optional

from django.http import HttpRequest
from ninja import Path, Query, Router, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found
from api.pagination import DEFAULT_LIMIT, paginate
from audits.models import Finding, Report, Run, Site
from ..schemas import FindingIn, FindingOut, PaginatedOut, ReportDetailOut, ReportOut, RunOut

router = Router(tags=["runs"])


def _run_out(run: Run) -> dict:
    return {
        "id":               run.pk,
        "status":           run.status,
        "page_count":       run.page_count,
        "total_tasks":      run.total_tasks,
        "completed_tasks":  run.completed_tasks,
        "created":          run.created,
    }


def _report_out(report: Report) -> dict:
    return {
        "id":       report.pk,
        "audit": {
            "slug":        report.audit.slug,
            "name":        report.audit.name,
            "description": report.audit.description,
        },
        "page_url": report.page.url,
        "error":    report.error,
        "created":  report.created,
    }


def _report_detail_out(report: Report, request: HttpRequest) -> dict:
    def file_url(field):
        if field and field.name:
            return request.build_absolute_uri(field.url)
        return None

    return {
        **_report_out(report),
        "data":             report.data,
        "json_report_url":  file_url(report.json_report),
        "html_report_url":  file_url(report.html_report),
    }


def _finding_out(finding: Finding) -> dict:
    return {
        "id":          finding.pk,
        "type":        finding.type,
        "title":       finding.title,
        "description": finding.description,
        "url":         finding.url,
        "severity":    finding.severity,
        "source":      finding.source,
        "data":        finding.data,
        "report_id":   finding.report_id,
        "page_url":    finding.page.url,
        "created":     finding.created,
    }


@router.get(
    "/",
    auth=bearer_auth,
    response={200: PaginatedOut[RunOut], 404: ErrorResponse},
    summary="List runs for a site",
    description="Returns runs newest-first. Filter by ?status= (running, complete, failed).",
)
def list_runs(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    status: Optional[str] = Query(None, description="Filter by status: running, complete, failed"),
    limit: int = Query(DEFAULT_LIMIT, description="Maximum runs to return (max 100)"),
    cursor: Optional[str] = Query(None, description="Pagination cursor from a previous response"),
):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    qs = Run.objects.filter(job__site=site).order_by("-pk")
    if status:
        qs = qs.filter(status=status)

    result = paginate(qs, limit, cursor, hint=f"GET /api/sites/{slug}/runs/?cursor=<next_cursor>")
    result["items"] = [_run_out(r) for r in result["items"]]
    return Status(200, result)


@router.get(
    "/{run_id}/",
    auth=bearer_auth,
    response={200: RunOut, 404: ErrorResponse},
    summary="Get a run",
)
def get_run(request: HttpRequest, slug: Annotated[str, Path(...)], run_id: int):
    try:
        run = Run.objects.get(pk=run_id, job__site__slug=slug)
    except Run.DoesNotExist:
        return Status(404, not_found("run", str(run_id)))
    return Status(200, _run_out(run))


@router.get(
    "/{run_id}/reports/",
    auth=bearer_auth,
    response={200: PaginatedOut[ReportOut], 404: ErrorResponse},
    summary="List reports in a run",
    description="Returns all reports for the run. Filter by ?audit= to narrow to one audit type.",
)
def list_run_reports(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    run_id: int,
    audit: Optional[str] = Query(None, description="Filter to reports from this audit slug"),
    limit: int = Query(DEFAULT_LIMIT, description="Maximum reports to return (max 100)"),
    cursor: Optional[str] = Query(None, description="Pagination cursor from a previous response"),
):
    try:
        run = Run.objects.get(pk=run_id, job__site__slug=slug)
    except Run.DoesNotExist:
        return Status(404, not_found("run", str(run_id)))

    qs = (
        Report.objects.filter(run=run)
        .select_related("audit", "page")
        .order_by("-pk")
    )
    if audit:
        qs = qs.filter(audit__slug=audit)

    result = paginate(qs, limit, cursor)
    result["items"] = [_report_out(r) for r in result["items"]]
    return Status(200, result)


@router.get(
    "/{run_id}/reports/{report_id}/",
    auth=bearer_auth,
    response={200: ReportDetailOut, 404: ErrorResponse},
    summary="Get a report",
    description=(
        "Returns the full report including raw audit data. "
        "For Lighthouse reports the data is in the file — use json_report_url to download it. "
        "For header and page-weight reports the data field contains the structured output."
    ),
)
def get_report(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    run_id: int,
    report_id: int,
):
    try:
        report = (
            Report.objects
            .select_related("audit", "page")
            .get(pk=report_id, run_id=run_id, run__job__site__slug=slug)
        )
    except Report.DoesNotExist:
        return Status(404, not_found("report", str(report_id)))
    return Status(200, _report_detail_out(report, request))


@router.post(
    "/{run_id}/reports/{report_id}/findings/",
    auth=bearer_auth,
    response={201: FindingOut, 404: ErrorResponse, 422: ErrorResponse},
    summary="Create a finding for a report",
    description=(
        "Attach a finding to a report. The finding's page is derived from the report. "
        "Use this to upload findings generated by secondary processing or external agents."
    ),
)
def create_finding(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    run_id: int,
    report_id: int,
    payload: FindingIn,
):
    try:
        report = (
            Report.objects
            .select_related("page")
            .get(pk=report_id, run_id=run_id, run__job__site__slug=slug)
        )
    except Report.DoesNotExist:
        return Status(404, not_found("report", str(report_id)))

    finding = Finding.objects.create(
        report=report,
        page=report.page,
        type=payload.type,
        title=payload.title,
        description=payload.description,
        url=payload.url,
        severity=payload.severity,
        source=payload.source,
        data=payload.data,
    )
    return Status(201, _finding_out(finding))
