"""Lighthouse API router — registered in api/api.py."""
from typing import Annotated, Any, Optional

from django.db.models import Avg, Count, Q
from django.http import HttpRequest
from django.urls import reverse
from ninja import Path, Query, Router, Schema, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found, invalid_field
from api.pagination import DEFAULT_LIMIT, paginate

from .models import Job, Page, Run
from .models.audit import PageCategory
from .models.rating import Rating

router = Router(tags=["lighthouse"])

VALID_RATINGS    = ["poor", "needs-improvement", "good"]
VALID_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class JobOut(Schema):
    id: int
    site_slug: str
    platform: str
    cat_performance: bool
    cat_accessibility: bool
    cat_best_practices: bool
    cat_seo: bool
    environment: str
    crontab: str
    enabled: bool

class CategorySummary(Schema):
    score: Optional[float]
    rating: Optional[str]
    poor: int
    needs: int
    good: int

class RunOut(Schema):
    id: int
    job_id: int
    status: str
    environment: str
    page_count: Optional[int]
    categories: dict[str, CategorySummary]
    created: Any

class PageListOut(Schema):
    id: int
    url: str
    audited: bool
    html_report_url: Optional[str]
    categories: dict[str, dict]

class AuditDetail(Schema):
    title: str; description: str; category: str
    score: Optional[int]; rating: Optional[str]
    value: Optional[float]; units: Optional[str]; details: Optional[Any]

class PageDetailOut(Schema):
    id: int; url: str; audited: bool
    html_report_url: Optional[str]
    categories: dict[str, dict]
    audits: dict[str, AuditDetail]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_site_or_404(slug):
    from sites.models import Site
    try:
        return Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return None


def _build_categories(run: Run) -> dict:
    cats = (
        PageCategory.objects.filter(page__run=run)
        .values("category_id", "title")
        .annotate(
            poor_count=Count("pk", filter=Q(rating=Rating.POOR)),
            needs_count=Count("pk", filter=Q(rating=Rating.NEEDS_IMPROVEMENT)),
            good_count=Count("pk", filter=Q(rating=Rating.GOOD)),
            score_avg=Avg("score"),
        )
    )

    def _rating(score):
        if score is None: return None
        s = int(score)
        return "good" if s >= 90 else "needs-improvement" if s >= 50 else "poor"

    return {
        c["category_id"]: {
            "score": round(c["score_avg"]) if c["score_avg"] is not None else None,
            "rating": _rating(c["score_avg"]),
            "poor": c["poor_count"],
            "needs": c["needs_count"],
            "good": c["good_count"],
        }
        for c in cats
    }


def _html_report_url(request, page: Page) -> Optional[str]:
    if page.html_report:
        return request.build_absolute_uri(
            reverse("admin:lighthouse-page-report", kwargs={"pk": page.pk})
        )
    return None


def _run_out(run: Run) -> dict:
    return {
        "id": run.pk,
        "job_id": run.job_id,
        "status": run.status,
        "environment": run.job.environment,
        "page_count": run.page_count,
        "categories": _build_categories(run),
        "created": run.created,
    }


def _job_out(job: Job) -> dict:
    return {
        "id": job.pk,
        "site_slug": job.site.slug,
        "platform": job.platform,
        "cat_performance": job.cat_performance,
        "cat_accessibility": job.cat_accessibility,
        "cat_best_practices": job.cat_best_practices,
        "cat_seo": job.cat_seo,
        "environment": job.environment,
        "crontab": job.crontab,
        "enabled": job.enabled,
    }


def _apply_run_filters(qs, cat_performance, cat_accessibility, cat_best_practices, cat_seo, environment, status):
    if cat_performance  is not None: qs = qs.filter(job__cat_performance=cat_performance)
    if cat_accessibility is not None: qs = qs.filter(job__cat_accessibility=cat_accessibility)
    if cat_best_practices is not None: qs = qs.filter(job__cat_best_practices=cat_best_practices)
    if cat_seo           is not None: qs = qs.filter(job__cat_seo=cat_seo)
    if environment: qs = qs.filter(job__environment=environment)
    if status:      qs = qs.filter(status=status)
    return qs


# ---------------------------------------------------------------------------
# Job endpoints
# ---------------------------------------------------------------------------

@router.get("/jobs/", auth=bearer_auth, response={200: list[JobOut], 404: ErrorResponse}, summary="List Lighthouse Jobs for a site")
def list_jobs(request: HttpRequest, slug: Annotated[str, Path(...)]):
    site = _get_site_or_404(slug)
    if not site:
        return Status(404, not_found("site", slug))
    return [_job_out(j) for j in Job.objects.filter(site=site).order_by("pk")]


@router.get("/jobs/{job_id}/", auth=bearer_auth, response={200: JobOut, 404: ErrorResponse}, summary="Get a Lighthouse Job")
def get_job(request: HttpRequest, slug: Annotated[str, Path(...)], job_id: int):
    site = _get_site_or_404(slug)
    if not site:
        return Status(404, not_found("site", slug))
    try:
        return _job_out(Job.objects.get(pk=job_id, site=site))
    except Job.DoesNotExist:
        return Status(404, not_found("job", str(job_id)))


# ---------------------------------------------------------------------------
# Run endpoints
# ---------------------------------------------------------------------------

@router.get("/runs/", auth=bearer_auth, response={200: Any, 404: ErrorResponse}, summary="List Lighthouse Runs for a site")
def list_runs(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    cat_performance:    Optional[bool] = Query(None),
    cat_accessibility:  Optional[bool] = Query(None),
    cat_best_practices: Optional[bool] = Query(None),
    cat_seo:            Optional[bool] = Query(None),
    environment: Optional[str] = Query(None),
    status:      Optional[str] = Query(None),
    limit: int = Query(DEFAULT_LIMIT),
    cursor: Optional[str] = Query(None),
):
    site = _get_site_or_404(slug)
    if not site:
        return Status(404, not_found("site", slug))
    qs = Run.objects.filter(job__site=site).select_related("job").order_by("-pk")
    qs = _apply_run_filters(qs, cat_performance, cat_accessibility, cat_best_practices, cat_seo, environment, status)
    result = paginate(qs, limit=limit, cursor=cursor, hint="Filter by ?cat_performance=true or ?environment=staging")
    result["items"] = [_run_out(r) for r in result["items"]]
    return result


@router.get("/runs/latest/", auth=bearer_auth, response={200: RunOut, 404: ErrorResponse}, summary="Most recent complete Lighthouse Run")
def latest_run(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    cat_performance:    Optional[bool] = Query(None),
    cat_accessibility:  Optional[bool] = Query(None),
    cat_best_practices: Optional[bool] = Query(None),
    cat_seo:            Optional[bool] = Query(None),
    environment: Optional[str] = Query(None),
):
    site = _get_site_or_404(slug)
    if not site:
        return Status(404, not_found("site", slug))
    qs = Run.objects.filter(job__site=site, status="complete").select_related("job").order_by("-pk")
    qs = _apply_run_filters(qs, cat_performance, cat_accessibility, cat_best_practices, cat_seo, environment, None)
    run = qs.first()
    if not run:
        return Status(404, not_found("run", "latest"))
    return _run_out(run)


@router.get("/runs/{run_id}/", auth=bearer_auth, response={200: RunOut, 404: ErrorResponse}, summary="Get a Lighthouse Run")
def get_run(request: HttpRequest, slug: Annotated[str, Path(...)], run_id: int):
    site = _get_site_or_404(slug)
    if not site:
        return Status(404, not_found("site", slug))
    try:
        run = Run.objects.select_related("job").get(pk=run_id, job__site=site)
        return _run_out(run)
    except Run.DoesNotExist:
        return Status(404, not_found("run", str(run_id)))


# ---------------------------------------------------------------------------
# Page endpoints
# ---------------------------------------------------------------------------

@router.get("/runs/{run_id}/pages/", auth=bearer_auth, response={200: Any, 404: ErrorResponse, 422: ErrorResponse}, summary="List pages in a Lighthouse Run")
def list_pages(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    run_id: int,
    rating:   Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    audit:    Optional[str] = Query(None),
    limit: int = Query(DEFAULT_LIMIT),
    cursor: Optional[str] = Query(None),
):
    if rating   and rating   not in VALID_RATINGS:    return Status(422, invalid_field("rating",   rating,   VALID_RATINGS))
    if category and category not in VALID_CATEGORIES: return Status(422, invalid_field("category", category, VALID_CATEGORIES))

    site = _get_site_or_404(slug)
    if not site:
        return Status(404, not_found("site", slug))
    try:
        run = Run.objects.get(pk=run_id, job__site=site)
    except Run.DoesNotExist:
        return Status(404, not_found("run", str(run_id)))

    qs = Page.objects.filter(run=run).prefetch_related("categories").order_by("url")
    if category and rating:
        qs = qs.filter(categories__category_id=category, categories__rating=rating).distinct()
    elif category:
        qs = qs.filter(categories__category_id=category).distinct()
    elif audit and rating:
        qs = qs.filter(audits__audit__audit_id=audit, audits__rating=rating).distinct()
    elif audit:
        qs = qs.filter(audits__audit__audit_id=audit).distinct()

    result = paginate(qs, limit=limit, cursor=cursor, hint="Add ?rating=poor&category=performance to narrow results")
    result["items"] = [
        {
            "id": p.pk,
            "url": p.url,
            "audited": p.audited,
            "html_report_url": _html_report_url(request, p),
            "categories": {c.category_id: {"score": c.score, "rating": c.rating} for c in p.categories.all()},
        }
        for p in result["items"]
    ]
    return result


@router.get("/runs/{run_id}/pages/{page_id}/", auth=bearer_auth, response={200: PageDetailOut, 404: ErrorResponse}, summary="Get full audit detail for a page")
def get_page(request: HttpRequest, slug: Annotated[str, Path(...)], run_id: int, page_id: int):
    site = _get_site_or_404(slug)
    if not site:
        return Status(404, not_found("site", slug))
    try:
        run  = Run.objects.get(pk=run_id, job__site=site)
        page = Page.objects.prefetch_related("categories", "audits__audit").get(pk=page_id, run=run)
    except (Run.DoesNotExist, Page.DoesNotExist):
        return Status(404, not_found("page", str(page_id)))

    return {
        "id": page.pk,
        "url": page.url,
        "audited": page.audited,
        "html_report_url": _html_report_url(request, page),
        "categories": {c.category_id: {"score": c.score, "rating": c.rating} for c in page.categories.all()},
        "audits": {
            pa.audit.audit_id: {
                "title": pa.audit.title,
                "description": pa.audit.description,
                "category": pa.audit.category_id,
                "score": pa.score,
                "rating": pa.rating,
                "value": pa.value,
                "units": pa.units or None,
                "details": pa.details,
            }
            for pa in page.audits.select_related("audit").all()
        },
    }


# ---------------------------------------------------------------------------
# Agent context (auto-discovered by introspection endpoint)
# ---------------------------------------------------------------------------

AGENT_CONTEXT = {
    "tool": "lighthouse",
    "jobs": {
        "list": "GET /api/sites/{slug}/lighthouse/jobs/",
        "get":  "GET /api/sites/{slug}/lighthouse/jobs/{id}/",
    },
    "runs": {
        "list":        "GET /api/sites/{slug}/lighthouse/runs/",
        "latest":      "GET /api/sites/{slug}/lighthouse/runs/latest/",
        "get":         "GET /api/sites/{slug}/lighthouse/runs/{id}/",
        "pages":       "GET /api/sites/{slug}/lighthouse/runs/{id}/pages/",
        "page_detail": "GET /api/sites/{slug}/lighthouse/runs/{id}/pages/{page_id}/",
    },
    "run_filters": {
        "cat_performance":    "bool — restrict to runs from Jobs with performance enabled",
        "cat_accessibility":  "bool",
        "cat_best_practices": "bool",
        "cat_seo":            "bool",
        "environment":        ["local", "staging", "production"],
        "status":             ["pending", "running", "complete", "failed"],
    },
    "page_filters": {
        "rating":   ["poor", "needs-improvement", "good"],
        "category": ["performance", "accessibility", "best-practices", "seo"],
        "audit":    "any audit_id from GET /api/audits/",
    },
}
