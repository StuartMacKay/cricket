from typing import Optional

from django.http import HttpRequest
from django.utils import timezone
from ninja import Router, Status

from sites.models import Scan
from ..auth import bearer_auth
from ..errors import ErrorResponse, not_found
from ..schemas import JobOut

router = Router(tags=["jobs"])

RETRY_AFTER_RUNNING = 30  # seconds
RECENT_JOB_HOURS = 24


def _job_out(scan: Scan) -> dict:
    now = timezone.now()
    duration_s = int((now - scan.created).total_seconds()) if scan.created else None

    retry_after = None
    result_url = None

    if scan.status in (Scan.Status.PENDING, Scan.Status.RUNNING):
        retry_after = RETRY_AFTER_RUNNING
    elif scan.status == Scan.Status.COMPLETE:
        result_url = f"/api/sites/{scan.site.slug}/scans/{scan.pk}/"

    return {
        "id": scan.pk,
        "kind": "scan",
        "status": scan.status,
        "started": scan.created,
        "duration_s": duration_s,
        "retry_after": retry_after,
        "result_url": result_url,
    }


@router.get("/", auth=bearer_auth, response=list[JobOut], summary="List recent jobs")
def list_jobs(request: HttpRequest):
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=RECENT_JOB_HOURS)
    qs = (
        Scan.objects.filter(created__gte=cutoff)
        .select_related("site")
        .order_by("-pk")[:50]
    )
    return [_job_out(s) for s in qs]


@router.get("/{job_id}/", auth=bearer_auth, response={200: JobOut, 404: ErrorResponse}, summary="Get a job's status")
def get_job(request: HttpRequest, job_id: int):
    try:
        scan = Scan.objects.select_related("site").get(pk=job_id)
    except Scan.DoesNotExist:
        return Status(404, not_found("job", str(job_id)))
    return _job_out(scan)
