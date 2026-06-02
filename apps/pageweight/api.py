"""Pageweight API router — registered in api/api.py."""
from typing import Annotated, Any, Optional

from django.http import HttpRequest
from ninja import Path, Query, Router, Schema, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found
from api.pagination import DEFAULT_LIMIT, paginate

from .models import Job, Page, Run

router = Router(tags=["pageweight"])


class JobOut(Schema):
    id: int; site_slug: str; device: str; environment: str; crontab: str; enabled: bool

class RunOut(Schema):
    id: int; job_id: int; status: str; device: str; environment: str
    page_count: Optional[int]; created: Any

class PageListOut(Schema):
    id: int; url: str; measured: bool
    total_transfer_size: int; total_resource_size: int; resource_count: int

class PageDetailOut(Schema):
    id: int; url: str; final_url: str; measured: bool; error: str
    total_transfer_size: int; total_resource_size: int; resource_count: int
    by_type: dict


def _get_site_or_404(slug):
    from sites.models import Site
    try:
        return Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return None


def _job_out(job):
    return {"id": job.pk, "site_slug": job.site.slug, "device": job.device, "environment": job.environment, "crontab": job.crontab, "enabled": job.enabled}

def _run_out(run):
    return {"id": run.pk, "job_id": run.job_id, "status": run.status, "device": run.job.device, "environment": run.job.environment, "page_count": run.page_count, "created": run.created}

def _by_type(page):
    types = ["document", "stylesheet", "script", "image", "font", "other"]
    return {t: {"transfer": getattr(page, f"{t}_transfer"), "size": getattr(page, f"{t}_size")} for t in types}


@router.get("/jobs/", auth=bearer_auth, response={200: list[JobOut], 404: ErrorResponse}, summary="List Pageweight Jobs")
def list_jobs(request: HttpRequest, slug: Annotated[str, Path(...)]):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    return [_job_out(j) for j in Job.objects.filter(site=site).order_by("pk")]


@router.get("/runs/", auth=bearer_auth, response={200: Any, 404: ErrorResponse}, summary="List Pageweight Runs")
def list_runs(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    device: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(DEFAULT_LIMIT),
    cursor: Optional[str] = Query(None),
):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    qs = Run.objects.filter(job__site=site).select_related("job").order_by("-pk")
    if device:       qs = qs.filter(job__device=device)
    if environment:  qs = qs.filter(job__environment=environment)
    if status:       qs = qs.filter(status=status)
    result = paginate(qs, limit=limit, cursor=cursor, hint="Filter by ?device=mobile or ?environment=staging")
    result["items"] = [_run_out(r) for r in result["items"]]
    return result


@router.get("/runs/latest/", auth=bearer_auth, response={200: RunOut, 404: ErrorResponse}, summary="Most recent complete Pageweight Run")
def latest_run(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    device: Optional[str] = Query(None),
    environment: Optional[str] = Query(None),
):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    qs = Run.objects.filter(job__site=site, status="complete").select_related("job").order_by("-pk")
    if device:      qs = qs.filter(job__device=device)
    if environment: qs = qs.filter(job__environment=environment)
    run = qs.first()
    if not run: return Status(404, not_found("run", "latest"))
    return _run_out(run)


@router.get("/runs/{run_id}/pages/", auth=bearer_auth, response={200: Any, 404: ErrorResponse}, summary="List page weight data for a Run")
def list_pages(request: HttpRequest, slug: Annotated[str, Path(...)], run_id: int, limit: int = Query(DEFAULT_LIMIT), cursor: Optional[str] = Query(None)):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    try:
        run = Run.objects.get(pk=run_id, job__site=site)
    except Run.DoesNotExist:
        return Status(404, not_found("run", str(run_id)))
    qs = Page.objects.filter(run=run).order_by("-total_transfer_size")
    result = paginate(qs, limit=limit, cursor=cursor, hint="Ordered by total transfer size descending")
    result["items"] = [
        {"id": p.pk, "url": p.url, "measured": p.measured,
         "total_transfer_size": p.total_transfer_size,
         "total_resource_size": p.total_resource_size,
         "resource_count": p.resource_count}
        for p in result["items"]
    ]
    return result


@router.get("/runs/{run_id}/pages/{page_id}/", auth=bearer_auth, response={200: PageDetailOut, 404: ErrorResponse}, summary="Get full page weight detail")
def get_page(request: HttpRequest, slug: Annotated[str, Path(...)], run_id: int, page_id: int):
    site = _get_site_or_404(slug)
    if not site: return Status(404, not_found("site", slug))
    try:
        run  = Run.objects.get(pk=run_id, job__site=site)
        page = Page.objects.get(pk=page_id, run=run)
    except (Run.DoesNotExist, Page.DoesNotExist):
        return Status(404, not_found("page", str(page_id)))
    return {
        "id": page.pk, "url": page.url, "final_url": page.final_url,
        "measured": page.measured, "error": page.error,
        "total_transfer_size": page.total_transfer_size,
        "total_resource_size": page.total_resource_size,
        "resource_count": page.resource_count,
        "by_type": _by_type(page),
    }


AGENT_CONTEXT = {
    "tool": "pageweight",
    "jobs": {
        "list": "GET /api/sites/{slug}/pageweight/jobs/",
    },
    "runs": {
        "list":        "GET /api/sites/{slug}/pageweight/runs/",
        "latest":      "GET /api/sites/{slug}/pageweight/runs/latest/",
        "pages":       "GET /api/sites/{slug}/pageweight/runs/{id}/pages/",
        "page_detail": "GET /api/sites/{slug}/pageweight/runs/{id}/pages/{page_id}/",
    },
    "run_filters": {
        "device":      ["mobile", "desktop"],
        "environment": ["local", "staging", "production"],
        "status":      ["pending", "running", "complete", "failed"],
    },
}
