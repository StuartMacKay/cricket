from typing import Optional

from django.http import HttpRequest
from django.utils import timezone
from ninja import Router

from lighthouse.models import Snapshot
from ..auth import bearer_auth
from ..errors import ErrorResponse, not_found
from ..schemas import JobOut

router = Router(tags=["jobs"])

RETRY_AFTER_RUNNING = 30  # seconds
RECENT_JOB_HOURS = 24


def _job_out(snapshot: Snapshot) -> dict:
    now = timezone.now()
    duration_s = None
    if snapshot.created:
        duration_s = int((now - snapshot.created).total_seconds())

    retry_after = None
    result_url = None

    if snapshot.status in (Snapshot.Status.PENDING, Snapshot.Status.RUNNING):
        retry_after = RETRY_AFTER_RUNNING
    elif snapshot.status == Snapshot.Status.COMPLETE:
        result_url = f"/api/sites/{snapshot.site.slug}/snapshots/{snapshot.pk}/"

    return {
        "id": snapshot.pk,
        "kind": "snapshot",
        "status": snapshot.status,
        "started": snapshot.created,
        "duration_s": duration_s,
        "retry_after": retry_after,
        "result_url": result_url,
    }


@router.get("/", auth=bearer_auth, response=list[JobOut], summary="List recent jobs")
def list_jobs(request: HttpRequest):
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=RECENT_JOB_HOURS)
    qs = (
        Snapshot.objects.filter(
            created__gte=cutoff
        )
        .select_related("site")
        .order_by("-pk")[:50]
    )
    return [_job_out(s) for s in qs]


@router.get("/{job_id}/", auth=bearer_auth, response={200: JobOut, 404: ErrorResponse}, summary="Get a job's status")
def get_job(request: HttpRequest, job_id: int):
    try:
        snapshot = Snapshot.objects.select_related("site").get(pk=job_id)
    except Snapshot.DoesNotExist:
        return 404, not_found("job", str(job_id))
    return _job_out(snapshot)
