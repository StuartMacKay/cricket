from typing import Annotated, Optional

from django.http import HttpRequest
from django.urls import reverse
from ninja import Path, Query, Router, Status

from lighthouse.models import PageCategory, PageResult
from sites.models import Page, Site, Scan
from ..auth import bearer_auth
from ..errors import ErrorResponse, invalid_field, not_found
from ..pagination import DEFAULT_LIMIT, paginate
from ..schemas import PageDetailOut, PaginatedOut

router = Router(tags=["pages"])

VALID_RATINGS = ["poor", "needs-improvement", "good"]
VALID_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]


def _html_report_url(request: HttpRequest, page: Page) -> Optional[str]:
    try:
        result = page.lighthouse_result
        if result.html_report:
            return request.build_absolute_uri(
                reverse("admin:lighthouse-page-report", kwargs={"pk": result.pk})
            )
    except PageResult.DoesNotExist:
        pass
    return None


def _page_categories(page: Page) -> dict:
    return {
        cat.category_id: {"score": cat.score, "rating": cat.rating}
        for cat in page.lighthouse_categories.all()
    }


def _page_audited(page: Page) -> bool:
    try:
        return page.lighthouse_result.audited
    except PageResult.DoesNotExist:
        return False


@router.get("/", auth=bearer_auth, response={200: PaginatedOut, 404: ErrorResponse, 422: ErrorResponse}, summary="List pages for a scan")
def list_pages(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    scan_id: Annotated[int, Path(...)],
    rating: Optional[str] = Query(None, description="Filter by rating: poor, needs-improvement, good"),
    category: Optional[str] = Query(None, description="Filter by category"),
    audit: Optional[str] = Query(None, description="Filter by audit ID"),
    limit: int = Query(DEFAULT_LIMIT),
    cursor: Optional[str] = Query(None),
):
    if rating and rating not in VALID_RATINGS:
        return Status(422, invalid_field("rating", rating, VALID_RATINGS))
    if category and category not in VALID_CATEGORIES:
        return Status(422, invalid_field("category", category, VALID_CATEGORIES))

    try:
        site = Site.objects.get(slug=slug)
        scan = Scan.objects.get(pk=scan_id, site=site)
    except (Site.DoesNotExist, Scan.DoesNotExist):
        return Status(404, not_found("scan", str(scan_id)))

    qs = (
        Page.objects.filter(scan=scan)
        .prefetch_related("lighthouse_categories")
        .order_by("url")
    )

    if category and rating:
        qs = qs.filter(
            lighthouse_categories__category_id=category,
            lighthouse_categories__rating=rating,
        ).distinct()
    elif category:
        qs = qs.filter(lighthouse_categories__category_id=category).distinct()
    elif audit and rating:
        qs = qs.filter(
            lighthouse_audits__audit__audit_id=audit,
            lighthouse_audits__rating=rating,
        ).distinct()
    elif audit:
        qs = qs.filter(lighthouse_audits__audit__audit_id=audit).distinct()

    hints = []
    if not rating:
        hints.append("Add ?rating=poor to narrow to failing pages only")
    if not category:
        hints.append("Add ?category=performance to filter by category")
    hint = " | ".join(hints)

    result = paginate(qs, limit=limit, cursor=cursor, hint=hint)
    result["items"] = [
        {
            "id": page.pk,
            "url": page.url,
            "audited": _page_audited(page),
            "html_report_url": _html_report_url(request, page),
            "categories": _page_categories(page),
        }
        for page in result["items"]
    ]
    return result


@router.get("/{page_id}/", auth=bearer_auth, response={200: PageDetailOut, 404: ErrorResponse}, summary="Get a page with full audit detail")
def get_page(request: HttpRequest, slug: Annotated[str, Path(...)], scan_id: Annotated[int, Path(...)], page_id: int):
    try:
        site = Site.objects.get(slug=slug)
        scan = Scan.objects.get(pk=scan_id, site=site)
        page = Page.objects.prefetch_related(
            "lighthouse_categories", "lighthouse_audits__audit"
        ).get(pk=page_id, scan=scan)
    except (Site.DoesNotExist, Scan.DoesNotExist, Page.DoesNotExist):
        return Status(404, not_found("page", str(page_id)))

    categories = _page_categories(page)

    audits = {}
    for page_audit in page.lighthouse_audits.select_related("audit").all():
        audit_def = page_audit.audit
        audits[audit_def.audit_id] = {
            "title": audit_def.title,
            "description": audit_def.description,
            "category": audit_def.category_id,
            "score": page_audit.score,
            "rating": page_audit.rating,
            "value": page_audit.value,
            "units": page_audit.units or None,
            "details": page_audit.details,
        }

    return {
        "id": page.pk,
        "url": page.url,
        "audited": _page_audited(page),
        "html_report_url": _html_report_url(request, page),
        "categories": categories,
        "audits": audits,
    }
