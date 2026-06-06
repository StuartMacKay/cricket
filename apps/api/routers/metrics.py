from typing import Annotated, Optional

from django.http import HttpRequest
from ninja import Path, Query, Router, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, invalid_field, not_found
from api.pagination import MAX_LIMIT
from audits.models import Definition, Metric, Run, Site
from ..schemas import PageMetricOut

router = Router(tags=["metrics"])

VALID_ORDER = ["score_asc", "score_desc", "value_asc", "value_desc"]


def _page_metric_out(metric: Metric) -> dict:
    return {
        "id":          metric.pk,
        "page_id":     metric.page_id,
        "page_url":    metric.page.url,
        "definition": {
            "slug":        metric.definition.slug,
            "name":        metric.definition.name,
            "description": metric.definition.description,
            "weight":      metric.definition.weight,
            "audit": {
                "slug":        metric.definition.audit.slug,
                "name":        metric.definition.audit.name,
                "description": metric.definition.audit.description,
            },
        },
        "value":       metric.value,
        "units":       metric.units,
        "score":       metric.score,
        "rating":      metric.rating,
        "run_id":      metric.report.run_id,
        "measured":    metric.measured,
    }


@router.get(
    "/",
    auth=bearer_auth,
    response={200: list[PageMetricOut], 404: ErrorResponse, 422: ErrorResponse},
    summary="Rank pages by metric value",
    description=(
        "Returns the most recent value of a metric for each page on the site, "
        "ranked by score or raw value. Useful for finding the best or worst "
        "performing pages for a given metric. "
        "?order=score_asc (default) returns the lowest-scoring pages first. "
        "Only pages that have at least one completed run are included."
    ),
)
def rank_pages_by_metric(
    request: HttpRequest,
    slug: Annotated[str, Path(...)],
    definition: str = Query(..., description="Definition slug to rank pages by"),
    order: str = Query("score_asc", description="Sort order: score_asc, score_desc, value_asc, value_desc"),
    limit: int = Query(10, description=f"Number of results to return (max {MAX_LIMIT})"),
):
    try:
        site = Site.objects.get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    try:
        Definition.objects.get(slug=definition)
    except Definition.DoesNotExist:
        return Status(404, not_found("definition", definition))

    if order not in VALID_ORDER:
        return Status(422, invalid_field("order", order, VALID_ORDER))

    limit = min(max(1, limit), MAX_LIMIT)

    all_metrics = (
        Metric.objects.filter(
            page__site=site,
            definition__slug=definition,
            report__run__status=Run.Status.COMPLETE,
        )
        .select_related("definition", "definition__audit", "page")
        .order_by("page_id", "-measured")
    )

    seen = set()
    latest_per_page = []
    for metric in all_metrics:
        page_id = metric.page_id
        if page_id not in seen:
            seen.add(page_id)
            latest_per_page.append(metric)

    if order == "score_asc":
        latest_per_page.sort(key=lambda m: (m.score is None, m.score or 0))
    elif order == "score_desc":
        latest_per_page.sort(key=lambda m: (m.score is None, -(m.score or 0)))
    elif order == "value_asc":
        latest_per_page.sort(key=lambda m: (m.value is None, m.value or 0))
    elif order == "value_desc":
        latest_per_page.sort(key=lambda m: (m.value is None, -(m.value or 0)))

    return Status(200, [_page_metric_out(m) for m in latest_per_page[:limit]])
