from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar

from ninja import Schema

T = TypeVar("T")


class PaginatedOut(Schema, Generic[T]):
    items: List[T]
    count: int
    limit: int
    truncated: bool
    next_cursor: Optional[str]
    hint: str


class AuditOut(Schema):
    slug: str
    name: str
    description: str


class DefinitionOut(Schema):
    slug: str
    name: str
    description: str
    weight: Optional[float]
    audit: AuditOut


class SiteOut(Schema):
    slug: str
    name: str
    url: str
    environment: str


class JobOut(Schema):
    id: int
    name: str
    description: str
    device: str
    schedule: str
    enabled: bool
    executed: Optional[datetime]
    audits: list[AuditOut]
    created: datetime


class PageOut(Schema):
    id: int
    url: str
    site_slug: str


class RunOut(Schema):
    id: int
    status: str
    page_count: Optional[int]
    total_tasks: int
    completed_tasks: int
    created: datetime


class ReportOut(Schema):
    id: int
    audit: AuditOut
    page_url: str
    error: str
    created: datetime


class ReportDetailOut(Schema):
    id: int
    audit: AuditOut
    page_url: str
    error: str
    created: datetime
    data: Any
    json_report_url: Optional[str]
    html_report_url: Optional[str]


class MetricOut(Schema):
    id: int
    definition: DefinitionOut
    value: Optional[float]
    units: str
    score: Optional[int]
    rating: Optional[str]
    run_id: int
    measured: Optional[datetime]


class PageMetricOut(Schema):
    """A metric annotated with the page it came from — used in cross-page queries."""
    id: int
    page_id: int
    page_url: str
    definition: DefinitionOut
    value: Optional[float]
    units: str
    score: Optional[int]
    rating: Optional[str]
    run_id: int
    measured: Optional[datetime]


class FindingOut(Schema):
    id: int
    type: str
    title: str
    description: str
    url: str
    severity: str
    source: str
    data: Any
    report_id: int
    page_url: str
    created: datetime


class FindingIn(Schema):
    type: str
    title: str
    description: str = ""
    url: str = ""
    severity: str = "warning"
    source: str = ""
    data: Optional[Any] = None
