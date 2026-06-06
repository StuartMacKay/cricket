from django.http import HttpRequest
from ninja import Router, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found
from audits.models import Site
from ..schemas import SiteOut

router = Router(tags=["sites"])


def _site_out(site: Site) -> dict:
    return {
        "slug":        site.slug,
        "name":        site.name,
        "url":         site.url,
        "environment": site.environment,
    }


@router.get(
    "/",
    auth=bearer_auth,
    response=list[SiteOut],
    summary="List sites",
    description="Returns all sites ordered by name.",
)
def list_sites(request: HttpRequest):
    return [_site_out(s) for s in Site.objects.order_by("name")]


@router.get(
    "/{slug}/",
    auth=bearer_auth,
    response={200: SiteOut, 404: ErrorResponse},
    summary="Get a site",
)
def get_site(request: HttpRequest, slug: str):
    try:
        return Status(200, _site_out(Site.objects.get(slug=slug)))
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))
