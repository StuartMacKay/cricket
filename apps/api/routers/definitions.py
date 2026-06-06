from django.http import HttpRequest
from ninja import Router, Status

from api.auth import bearer_auth
from api.errors import ErrorResponse, not_found
from audits.models import Definition
from ..schemas import DefinitionOut

router = Router(tags=["definitions"])


def _definition_out(definition: Definition) -> dict:
    return {
        "slug":        definition.slug,
        "name":        definition.name,
        "description": definition.description,
        "weight":      definition.weight,
        "audit": {
            "slug":        definition.audit.slug,
            "name":        definition.audit.name,
            "description": definition.audit.description,
        },
    }


@router.get(
    "/",
    auth=bearer_auth,
    response=list[DefinitionOut],
    summary="List metric definitions",
    description="All metric definitions across all audits, ordered by audit then name.",
)
def list_definitions(request: HttpRequest):
    qs = Definition.objects.select_related("audit").order_by("audit__name", "name")
    return [_definition_out(d) for d in qs]


@router.get(
    "/{slug}/",
    auth=bearer_auth,
    response={200: DefinitionOut, 404: ErrorResponse},
    summary="Get a metric definition",
)
def get_definition(request: HttpRequest, slug: str):
    try:
        return Status(200, _definition_out(Definition.objects.select_related("audit").get(slug=slug)))
    except Definition.DoesNotExist:
        return Status(404, not_found("definition", slug))
