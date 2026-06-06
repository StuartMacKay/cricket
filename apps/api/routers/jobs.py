from typing import Annotated

from django.http import HttpRequest
from ninja import Path, Router, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found
from audits.models import Job, Site
from ..schemas import JobOut

router = Router(tags=["jobs"])


def _job_out(job: Job) -> dict:
    return {
        "id":          job.pk,
        "name":        job.name,
        "description": job.description,
        "device":      job.device,
        "schedule":    job.schedule,
        "enabled":     job.enabled,
        "executed":    job.executed,
        "audits":      [
            {"slug": a.slug, "name": a.name, "description": a.description}
            for a in job.audits.all()
        ],
        "created":     job.created,
    }


@router.get(
    "/",
    auth=bearer_auth,
    response={200: list[JobOut], 404: ErrorResponse},
    summary="List jobs for a site",
    description="Returns all jobs for the site, including their audit configuration and schedule.",
)
def list_jobs(request: HttpRequest, slug: Annotated[str, Path(...)]):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    qs = Job.objects.filter(site=site).prefetch_related("audits").order_by("name")
    return Status(200, [_job_out(j) for j in qs])


@router.get(
    "/{job_id}/",
    auth=bearer_auth,
    response={200: JobOut, 404: ErrorResponse},
    summary="Get a job",
)
def get_job(request: HttpRequest, slug: Annotated[str, Path(...)], job_id: int):
    try:
        job = Job.objects.prefetch_related("audits").get(pk=job_id, site__slug=slug)
    except Job.DoesNotExist:
        return Status(404, not_found("job", str(job_id)))
    return Status(200, _job_out(job))
