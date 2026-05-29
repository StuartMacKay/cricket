from typing import Annotated, Optional

from django.http import HttpRequest
from django.utils import timezone
from ninja import Path, Query, Router

from lighthouse.models import Site, Snapshot, SnapshotCategory
from ..auth import bearer_auth
from ..errors import ErrorResponse, no_complete_snapshot, not_found, snapshot_in_progress
from ..pagination import DEFAULT_LIMIT, paginate
from ..schemas import SnapshotOut, SnapshotTriggerIn, SnapshotTriggerOut

router = Router(tags=["snapshots"])


def _build_categories(snapshot: Snapshot) -> dict:
    cats = {}
    for cat in snapshot.category_results.all():
        cats[cat.category_id] = {
            "score": round(cat.score_avg) if cat.score_avg is not None else None,
            "rating": _rating_from_score(cat.score_avg),
            "poor": cat.poor_count,
            "needs": cat.needs_count,
            "good": cat.good_count,
        }
    return cats


def _rating_from_score(score) -> Optional[str]:
    if score is None:
        return None
    score = int(score)
    if score >= 90:
        return "good"
    if score >= 50:
        return "needs-improvement"
    return "poor"


def _snapshot_out(snapshot: Snapshot) -> dict:
    return {
        "id": snapshot.pk,
        "created": snapshot.created,
        "status": snapshot.status,
        "platform": snapshot.platform,
        "page_count": snapshot.page_count,
        "categories": _build_categories(snapshot),
    }


@router.get("/", auth=bearer_auth, response={200: dict, 404: ErrorResponse}, summary="List snapshots for a site")
def list_snapshots(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    limit: int = Query(DEFAULT_LIMIT),
    cursor: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return 404, not_found("site", slug)

    qs = (
        Snapshot.objects.filter(site=site)
        .prefetch_related("category_results")
        .order_by("-pk")
    )
    if status:
        qs = qs.filter(status=status)

    result = paginate(
        qs,
        limit=limit,
        cursor=cursor,
        hint="Add ?status=complete to see only completed snapshots",
    )
    result["items"] = [_snapshot_out(s) for s in result["items"]]
    return result


@router.get("/latest/", auth=bearer_auth, response={200: dict, 404: ErrorResponse}, summary="Most recent complete snapshot")
def latest_snapshot(request: HttpRequest, slug: Annotated[str, Path(...)]):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return 404, not_found("site", slug)

    snapshot = (
        Snapshot.objects.filter(site=site, status=Snapshot.Status.COMPLETE)
        .prefetch_related("category_results")
        .order_by("-pk")
        .first()
    )
    if not snapshot:
        return 404, no_complete_snapshot(slug)

    return _snapshot_out(snapshot)


@router.get("/{snapshot_id}/", auth=bearer_auth, response={200: dict, 404: ErrorResponse}, summary="Get a snapshot")
def get_snapshot(request: HttpRequest, slug: Annotated[str, Path(...)], snapshot_id: int):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return 404, not_found("site", slug)

    try:
        snapshot = (
            Snapshot.objects.filter(site=site)
            .prefetch_related("category_results")
            .get(pk=snapshot_id)
        )
    except Snapshot.DoesNotExist:
        return 404, not_found("snapshot", str(snapshot_id))

    return _snapshot_out(snapshot)


@router.post("/", auth=bearer_auth, response={202: SnapshotTriggerOut, 409: ErrorResponse, 404: ErrorResponse}, summary="Trigger a new snapshot")
def create_snapshot(request: HttpRequest, slug: Annotated[str, Path(...)], body: SnapshotTriggerIn):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return 404, not_found("site", slug)

    # Check for in-flight snapshot unless force=True
    if not body.force:
        in_flight = Snapshot.objects.filter(
            site=site,
            status__in=[Snapshot.Status.PENDING, Snapshot.Status.RUNNING],
        ).order_by("-pk").first()
        if in_flight:
            return 409, snapshot_in_progress(in_flight.pk)

    # Trigger the new snapshot
    from lighthouse.tasks import take_snapshot
    snapshot = site.create_snapshot()

    # Store webhook_url if provided
    if body.webhook_url:
        snapshot.webhook_url = body.webhook_url
        snapshot.save(update_fields=["webhook_url"])

    take_snapshot.delay(site.pk)

    return 202, {
        "id": snapshot.pk,
        "status": snapshot.status,
        "existing": False,
        "poll_url": f"/api/jobs/{snapshot.pk}/",
        "webhook_url": body.webhook_url,
    }
