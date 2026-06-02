"""Headers API router — registered in api/api.py."""
from typing import Annotated, Any, Optional

from django.http import HttpRequest
from ninja import Path, Query, Router, Schema, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found
from api.pagination import DEFAULT_LIMIT, paginate

from .models import Job, Page, Run

router = Router(tags=["headers"])


class JobOut(Schema):
    id: int; site_slug: str; environment: str; crontab: str; enabled: bool

class RunOut(Schema):
    id: int; job_id: int; status: str; environment: str
    page_count: Optional[int]; created: Any

class PageOut(Schema):
    id: int; url: str; final_url: str
    status_code: Optional[int]; redirect_count: int
    headers: dict; error: str


def _get_site_or_404(slug):
    from sites.models import Site
    try:
        return Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return None


def _job_out(job):
    return {"id": job.pk, "site_slug": job.site.slug, "environment": job.environment, "crontab": job.crontab, "enabled": job.enabled}

def _run_out(run):
    return {"id": run.pk, "job_id": run.job_id, "status": run.status, "environment": run.job.environment, "page_count": run.page_count, "created": run.created}


@router.get("/jobs/", auth=bearer_auth, response={200: list[JobOut], 404: ErrorResponse}, summary="List Headers Jobs")
def list_jobs(request: HttpRequest, slug: Annotated[str, Path(...)]):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    return [_job_out(j) for j in Job.objects.filter(site=site).order_by("pk")]


@router.get("/runs/", auth=bearer_auth, response={200: Any, 404: ErrorResponse}, summary="List Headers Runs")
def list_runs(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    environment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(DEFAULT_LIMIT),
    cursor: Optional[str] = Query(None),
):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    qs = Run.objects.filter(job__site=site).select_related("job").order_by("-pk")
    if environment: qs = qs.filter(job__environment=environment)
    if status:      qs = qs.filter(status=status)
    result = paginate(qs, limit=limit, cursor=cursor, hint="Filter by ?environment=staging")
    result["items"] = [_run_out(r) for r in result["items"]]
    return result


@router.get("/runs/latest/", auth=bearer_auth, response={200: RunOut, 404: ErrorResponse}, summary="Most recent complete Headers Run")
def latest_run(request: HttpRequest, slug: Annotated[str, Path(...)], environment: Optional[str] = Query(None)):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    qs = Run.objects.filter(job__site=site, status="complete").select_related("job").order_by("-pk")
    if environment: qs = qs.filter(job__environment=environment)
    run = qs.first()
    if not run: return Status(404, not_found("run", "latest"))
    return _run_out(run)


@router.get("/runs/{run_id}/pages/", auth=bearer_auth, response={200: Any, 404: ErrorResponse}, summary="List header data for all pages in a Run")
def list_pages(request: HttpRequest, slug: Annotated[str, Path(...)], run_id: int, limit: int = Query(DEFAULT_LIMIT), cursor: Optional[str] = Query(None)):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    try:
        run = Run.objects.get(pk=run_id, job__site=site)
    except Run.DoesNotExist:
        return Status(404, not_found("run", str(run_id)))
    qs = Page.objects.filter(run=run).order_by("url")
    result = paginate(qs, limit=limit, cursor=cursor, hint="")
    result["items"] = [
        {"id": p.pk, "url": p.url, "final_url": p.final_url, "status_code": p.status_code,
         "redirect_count": p.redirect_count, "headers": p.headers, "error": p.error}
        for p in result["items"]
    ]
    return result


AGENT_CONTEXT = {
    "tool": "headers",
    "jobs": {
        "list": "GET /api/sites/{slug}/headers/jobs/",
    },
    "runs": {
        "list":   "GET /api/sites/{slug}/headers/runs/",
        "latest": "GET /api/sites/{slug}/headers/runs/latest/",
        "pages":  "GET /api/sites/{slug}/headers/runs/{id}/pages/",
    },
    "run_filters": {
        "environment": ["local", "staging", "production"],
        "status":      ["pending", "running", "complete", "failed"],
    },
}
