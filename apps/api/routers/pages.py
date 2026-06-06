from typing import Annotated, Optional

from django.http import HttpRequest
from ninja import Path, Query, Router, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found
from api.pagination import DEFAULT_LIMIT, MAX_LIMIT, paginate
from audits.models import Finding, Metric, Page, Run, Site
from ..schemas import FindingOut, MetricOut, PageOut, PaginatedOut

router = Router(tags=["pages"])


def _page_out(page: Page) -> dict:
    return {
        "id":        page.pk,
        "url":       page.url,
        "site_slug": page.site.slug,
    }


def _metric_out(metric: Metric) -> dict:
    return {
        "id":          metric.pk,
        "definition": {
            "slug":        metric.definition.slug,
            "name":        metric.definition.name,
            "description": metric.definition.description,
            "weight":      metric.definition.weight,
            "audit": {
                "slug":        metric.definition.audit.slug,
                "name":        metric.definition.audit.name,
                "description": metric.definition.audit.description,
            },
        },
        "value":       metric.value,
        "units":       metric.units,
        "score":       metric.score,
        "rating":      metric.rating,
        "run_id":      metric.report.run_id,
        "measured":    metric.measured,
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
    response={200: PaginatedOut[PageOut], 404: ErrorResponse},
    summary="List pages for a site",
)
def list_pages(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    limit: int = Query(DEFAULT_LIMIT, description="Maximum pages to return (max 100)"),
    cursor: Optional[str] = Query(None, description="Pagination cursor from a previous response"),
):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    qs = Page.objects.filter(site=site).order_by("-pk")
    result = paginate(qs, limit, cursor, hint=f"GET /api/sites/{slug}/pages/?cursor=<next_cursor>")
    result["items"] = [_page_out(p) for p in result["items"]]
    return Status(200, result)


@router.get(
    "/{page_id}/",
    auth=bearer_auth,
    response={200: PageOut, 404: ErrorResponse},
    summary="Get a page",
)
def get_page(request: HttpRequest, slug: Annotated[str, Path(...)], page_id: int):
    try:
        page = Page.objects.select_related("site").get(pk=page_id, site__slug=slug)
    except Page.DoesNotExist:
        return Status(404, not_found("page", str(page_id)))
    return Status(200, _page_out(page))


@router.get(
    "/{page_id}/metrics/",
    auth=bearer_auth,
    response={200: list[MetricOut], 404: ErrorResponse},
    summary="Get metrics for a page",
    description=(
        "Returns one Metric per definition from the most recently completed Run for this page. "
        "Pass ?run_id= to query a specific run instead. "
        "Pass ?audit= to filter to metrics from one audit (e.g. ?audit=performance)."
    ),
)
def list_page_metrics(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    page_id: int,
    run_id: Optional[int] = Query(None, description="Specific run ID; defaults to the latest complete run"),
    audit: Optional[str] = Query(None, description="Filter to metrics from this audit slug"),
):
    try:
        page = Page.objects.select_related("site").get(pk=page_id, site__slug=slug)
    except Page.DoesNotExist:
        return Status(404, not_found("page", str(page_id)))

    if run_id is not None:
        run = Run.objects.filter(pk=run_id, reports__page=page).first()
        if run is None:
            return Status(404, not_found("run", str(run_id)))
    else:
        run = (
            Run.objects.filter(reports__page=page, status=Run.Status.COMPLETE)
            .order_by("-created")
            .first()
        )
        if run is None:
            return Status(200, [])

    qs = (
        Metric.objects.filter(page=page, report__run=run)
        .select_related("definition", "definition__audit")
        .order_by("definition__audit__name", "definition__name")
    )

    if audit:
        qs = qs.filter(definition__audit__slug=audit)

    return Status(200, [_metric_out(m) for m in qs])


@router.get(
    "/{page_id}/metrics/history/",
    auth=bearer_auth,
    response={200: list[MetricOut], 404: ErrorResponse},
    summary="Get metric history for a page",
    description=(
        "Returns all recorded metrics for a page across all completed runs, newest first. "
        "Pass ?definition= to focus on a single metric over time (e.g. largest-contentful-paint). "
        "Pass ?audit= to filter to one audit's metrics. "
        "Useful for trend analysis and regression detection."
    ),
)
def list_page_metric_history(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    page_id: int,
    definition: Optional[str] = Query(None, description="Filter to a specific definition slug"),
    audit: Optional[str] = Query(None, description="Filter to metrics from this audit slug"),
    limit: int = Query(50, description=f"Number of results to return (max {MAX_LIMIT})"),
):
    try:
        page = Page.objects.select_related("site").get(pk=page_id, site__slug=slug)
    except Page.DoesNotExist:
        return Status(404, not_found("page", str(page_id)))

    limit = min(max(1, limit), MAX_LIMIT)

    qs = (
        Metric.objects.filter(page=page, report__run__status=Run.Status.COMPLETE)
        .select_related("definition", "definition__audit")
        .order_by("-measured")
    )

    if definition:
        qs = qs.filter(definition__slug=definition)
    if audit:
        qs = qs.filter(definition__audit__slug=audit)

    return Status(200, [_metric_out(m) for m in qs[:limit]])


@router.get(
    "/{page_id}/findings/",
    auth=bearer_auth,
    response={200: list[FindingOut], 404: ErrorResponse},
    summary="Get findings for a page",
    description=(
        "Returns findings for a page, newest first. "
        "Pass ?type= to filter to a specific finding category (e.g. dead-link). "
        "Pass ?severity= to filter by severity (error, warning, info). "
        "Pass ?run_id= to limit to findings from a specific run's reports."
    ),
)
def list_page_findings(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    page_id: int,
    type: Optional[str] = Query(None, description="Filter by finding type slug"),
    severity: Optional[str] = Query(None, description="Filter by severity: error, warning, info"),
    run_id: Optional[int] = Query(None, description="Limit to findings from a specific run"),
    limit: int = Query(DEFAULT_LIMIT, description=f"Number of results to return (max {MAX_LIMIT})"),
):
    try:
        page = Page.objects.select_related("site").get(pk=page_id, site__slug=slug)
    except Page.DoesNotExist:
        return Status(404, not_found("page", str(page_id)))

    limit = min(max(1, limit), MAX_LIMIT)

    qs = (
        Finding.objects.filter(page=page)
        .select_related("page")
        .order_by("-created")
    )

    if type:
        qs = qs.filter(type=type)
    if severity:
        qs = qs.filter(severity=severity)
    if run_id is not None:
        qs = qs.filter(report__run_id=run_id)

    return Status(200, [_finding_out(f) for f in qs[:limit]])
