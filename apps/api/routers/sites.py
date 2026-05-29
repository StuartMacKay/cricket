from django.http import HttpRequest
from ninja import Router, Status

from lighthouse.models import Site
from ..auth import bearer_auth
from ..errors import ErrorResponse, not_found
from ..schemas import SiteOut

router = Router(tags=["sites"])


def _site_out(site: Site) -> dict:
    return {
        "slug": site.slug,
        "name": site.name,
        "url": site.url,
        "enabled": site.enabled,
        "snapped": site.snapped,
        "crontab": site.crontab,
        "current_snapshot_id": site.current_snapshot_id,
    }


@router.get("/", auth=bearer_auth, response=list[SiteOut], summary="List sites")
def list_sites(request: HttpRequest):
    api_key = request.auth
    qs = Site.objects.order_by("name").select_related("current_snapshot")
    if api_key and api_key.site_id:
        qs = qs.filter(pk=api_key.site_id)
    return [_site_out(s) for s in qs]


@router.get("/{slug}/", auth=bearer_auth, response={200: SiteOut, 403: ErrorResponse, 404: ErrorResponse}, summary="Get a site")
def get_site(request: HttpRequest, slug: str):
    api_key = request.auth
    try:
        site = Site.objects.select_related("current_snapshot").get(slug=slug)
    except Site.DoesNotExist:
        return Status(404, not_found("site", slug))

    if api_key and api_key.site_id and api_key.site_id != site.pk:
        return Status(403, {"error": {"code": "forbidden", "message": "This key does not have access to that site"}})

    return _site_out(site)
