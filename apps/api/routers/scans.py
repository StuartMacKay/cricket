from typing import Annotated, Optional

from django.db.models import Avg, Count, Q
from django.http import HttpRequest
from ninja import Path, Query, Router, Status

from lighthouse.models import PageCategory
from lighthouse.models.rating import Rating
from sites.models import Site, Scan
from ..auth import bearer_auth
from ..errors import ErrorResponse, no_complete_scan, not_found, scan_in_progress
from ..pagination import DEFAULT_LIMIT, paginate
from ..schemas import PaginatedOut, ScanOut, ScanTriggerIn, ScanTriggerOut

router = Router(tags=["scans"])


def _build_categories(scan: Scan) -> dict:
    cats = (
        PageCategory.objects.filter(page__scan=scan)
        .values("category_id", "title")
        .annotate(
            poor_count=Count("pk", filter=Q(rating=Rating.POOR)),
            needs_count=Count("pk", filter=Q(rating=Rating.NEEDS_IMPROVEMENT)),
            good_count=Count("pk", filter=Q(rating=Rating.GOOD)),
            score_avg=Avg("score"),
        )
    )

    def _rating_from_score(score) -> Optional[str]:
        if score is None:
            return None
        score = int(score)
        if score >= 90:
            return "good"
        if score >= 50:
            return "needs-improvement"
        return "poor"

    return {
        cat["category_id"]: {
            "score": round(cat["score_avg"]) if cat["score_avg"] is not None else None,
            "rating": _rating_from_score(cat["score_avg"]),
            "poor": cat["poor_count"],
            "needs": cat["needs_count"],
            "good": cat["good_count"],
        }
        for cat in cats
    }


def _scan_out(scan: Scan) -> dict:
    try:
        lh_run = scan.lighthouse_run.get()
        page_count = lh_run.page_count
    except Exception:
        page_count = None

    return {
        "id": scan.pk,
        "created": scan.created,
        "status": scan.status,
        "platform": scan.platform,
        "environment": scan.environment,
        "page_count": page_count,
        "categories": _build_categories(scan),
    }


@router.get("/", auth=bearer_auth, response={200: PaginatedOut, 404: ErrorResponse}, summary="List scans for a site")
def list_scans(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    limit: int = Query(DEFAULT_LIMIT),
    cursor: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    qs = Scan.objects.filter(site=site).order_by("-pk")
    if status:
        qs = qs.filter(status=status)
    if environment:
        qs = qs.filter(environment=environment)

    result = paginate(qs, limit=limit, cursor=cursor, hint="Add ?status=complete to see only completed scans")
    result["items"] = [_scan_out(s) for s in result["items"]]
    return result


@router.get("/latest/", auth=bearer_auth, response={200: ScanOut, 404: ErrorResponse}, summary="Most recent complete scan")
def latest_scan(request: HttpRequest, slug: Annotated[str, Path(...)]):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    scan = (
        Scan.objects.filter(site=site, status=Scan.Status.COMPLETE)
        .order_by("-pk")
        .first()
    )
    if not scan:
        return Status(404, no_complete_scan(slug))

    return _scan_out(scan)


@router.get("/{scan_id}/", auth=bearer_auth, response={200: ScanOut, 404: ErrorResponse}, summary="Get a scan")
def get_scan(request: HttpRequest, slug: Annotated[str, Path(...)], scan_id: int):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    try:
        scan = Scan.objects.get(pk=scan_id, site=site)
    except Scan.DoesNotExist:
        return Status(404, not_found("scan", str(scan_id)))

    return _scan_out(scan)


@router.post("/", auth=bearer_auth, response={202: ScanTriggerOut, 404: ErrorResponse, 409: ErrorResponse}, summary="Trigger a new scan")
def create_scan(request: HttpRequest, slug: Annotated[str, Path(...)], body: ScanTriggerIn):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    if not body.force:
        in_flight = Scan.objects.filter(
            site=site,
            status__in=[Scan.Status.PENDING, Scan.Status.RUNNING],
        ).order_by("-pk").first()
        if in_flight:
            return Status(409, scan_in_progress(in_flight.pk))

    from sites.tasks import take_site_scan

    scan = site.create_scan()

    if body.webhook_url:
        scan.webhook_url = body.webhook_url
        scan.save(update_fields=["webhook_url"])

    take_site_scan.delay(site.pk)

    return Status(202, {
        "id": scan.pk,
        "status": scan.status,
        "existing": False,
        "poll_url": f"/api/jobs/{scan.pk}/",
        "webhook_url": body.webhook_url,
    })
