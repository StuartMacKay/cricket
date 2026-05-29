from typing import Annotated, Optional

from django.http import HttpRequest
from django.urls import reverse
from ninja import Path, Query, Router, Status

from lighthouse.models import Page, Snapshot as LighthouseSnapshot
from sites.models import Site, Snapshot as SiteSnapshot
from ..auth import bearer_auth
from ..errors import ErrorResponse, invalid_field, not_found
from ..pagination import DEFAULT_LIMIT, paginate
from ..schemas import PageDetailOut, PaginatedOut

router = Router(tags=["pages"])

VALID_RATINGS = ["poor", "needs-improvement", "good"]
VALID_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]


def _html_report_url(request: HttpRequest, page: Page) -> Optional[str]:
    if page.html_report:
        return request.build_absolute_uri(
            reverse("admin:lighthouse-page-report", kwargs={"pk": page.pk})
        )
    return None


def _page_categories(page: Page) -> dict:
    return {
        cat.category_id: {"score": cat.score, "rating": cat.rating}
        for cat in page.categories.all()
    }


@router.get("/", auth=bearer_auth, response={200: PaginatedOut, 404: ErrorResponse, 422: ErrorResponse}, summary="List pages for a snapshot")
def list_pages(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    snapshot_id: Annotated[int, Path(...)],
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
        sites_snapshot = SiteSnapshot.objects.get(pk=snapshot_id, site=site)
    except (Site.DoesNotExist, SiteSnapshot.DoesNotExist):
        return Status(404, not_found("snapshot", str(snapshot_id)))

    lh_snapshot = sites_snapshot.lighthouse_snapshots.first()
    if not lh_snapshot:
        return Status(404, not_found("snapshot", str(snapshot_id)))

    qs = (
        Page.objects.filter(snapshot=lh_snapshot, audited=True)
        .prefetch_related("categories")
        .order_by("url")
    )

    if category and rating:
        qs = qs.filter(
            categories__category_id=category,
            categories__rating=rating,
        ).distinct()
    elif category:
        qs = qs.filter(categories__category_id=category).distinct()
    elif audit and rating:
        qs = qs.filter(
            audits__audit__audit_id=audit,
            audits__rating=rating,
        ).distinct()
    elif audit:
        qs = qs.filter(audits__audit__audit_id=audit).distinct()

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
            "audited": page.audited,
            "html_report_url": _html_report_url(request, page),
            "categories": _page_categories(page),
        }
        for page in result["items"]
    ]
    return result


@router.get("/{page_id}/", auth=bearer_auth, response={200: PageDetailOut, 404: ErrorResponse}, summary="Get a page with full audit detail")
def get_page(request: HttpRequest, slug: Annotated[str, Path(...)], snapshot_id: Annotated[int, Path(...)], page_id: int):
    try:
        site = Site.objects.get(slug=slug)
        sites_snapshot = SiteSnapshot.objects.get(pk=snapshot_id, site=site)
        lh_snapshot = sites_snapshot.lighthouse_snapshots.first()
        if not lh_snapshot:
            raise LighthouseSnapshot.DoesNotExist
        page = Page.objects.prefetch_related(
            "categories", "audits__audit"
        ).get(pk=page_id, snapshot=lh_snapshot)
    except (Site.DoesNotExist, SiteSnapshot.DoesNotExist, LighthouseSnapshot.DoesNotExist, Page.DoesNotExist):
        return Status(404, not_found("page", str(page_id)))

    categories = _page_categories(page)

    audits = {}
    for page_audit in page.audits.select_related("audit").all():
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
        "audited": page.audited,
        "html_report_url": _html_report_url(request, page),
        "categories": categories,
        "audits": audits,
    }
