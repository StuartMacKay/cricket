from typing import Optional

from django.db.models import Sum
from django.http import HttpRequest
from ninja import Query, Router, Status

from lighthouse.models import AuditDefinition, SnapshotAudit
from ..auth import bearer_auth
from ..errors import ErrorResponse, invalid_field, not_found
from ..schemas import AuditDefinitionOut, AuditDefinitionWithStats

router = Router(tags=["audits"])

VALID_SORT = ["audit_id", "fail_rate", "failing_pages"]


@router.get("/", auth=bearer_auth, response={200: list[AuditDefinitionWithStats], 422: ErrorResponse}, summary="List audit definitions")
def list_audits(
    request: HttpRequest,
    has_failures: bool = Query(False, description="Only return audits with at least one failing page"),
    sort: str = Query("audit_id", description="Sort by: audit_id, fail_rate, failing_pages"),
):
    if sort not in VALID_SORT:
        return Status(422, invalid_field("sort", sort, VALID_SORT))

    qs = AuditDefinition.objects.all()

    # Annotate with failure counts from SnapshotAudit
    qs = qs.annotate(
        total_failing=Sum("snapshot_audits__poor_count", default=0),
        total_needing=Sum("snapshot_audits__needs_count", default=0),
        total_good=Sum("snapshot_audits__good_count", default=0),
    )

    if has_failures:
        qs = qs.filter(total_failing__gt=0)

    results = []
    for audit in qs:
        total = (audit.total_failing or 0) + (audit.total_needing or 0) + (audit.total_good or 0)
        failing = (audit.total_failing or 0)
        fail_rate = round(failing / total, 3) if total > 0 else None
        results.append(
            AuditDefinitionWithStats(
                audit_id=audit.audit_id,
                category_id=audit.category_id,
                title=audit.title,
                description=audit.description,
                weight=audit.weight,
                fail_rate=fail_rate,
                failing_pages=failing if total > 0 else None,
            )
        )

    if sort == "fail_rate":
        results.sort(key=lambda x: x.fail_rate or 0, reverse=True)
    elif sort == "failing_pages":
        results.sort(key=lambda x: x.failing_pages or 0, reverse=True)
    else:
        results.sort(key=lambda x: x.audit_id)

    return results


@router.get("/{audit_id}/", auth=bearer_auth, response={200: AuditDefinitionOut, 404: ErrorResponse}, summary="Get an audit definition")
def get_audit(request: HttpRequest, audit_id: str):
    try:
        audit = AuditDefinition.objects.get(audit_id=audit_id)
    except AuditDefinition.DoesNotExist:
        return Status(404, not_found("audit", audit_id))
    return audit
