from datetime import datetime
from typing import Any, Literal, Optional

from ninja import Schema

RatingSlug = Literal["poor", "needs-improvement", "good"]
CategorySlug = Literal["performance", "accessibility", "best-practices", "seo"]
StatusSlug = Literal["pending", "running", "complete", "failed"]


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------


class SiteOut(Schema):
    slug: str
    name: str
    url: str
    enabled: bool
    platform: str
    snapped: Optional[datetime]
    crontab: str
    current_snapshot_id: Optional[int]


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------


class CategorySummary(Schema):
    score: Optional[float]
    rating: Optional[str]
    poor: int
    needs: int
    good: int


class SnapshotOut(Schema):
    id: int
    created: datetime
    status: str
    platform: str
    page_count: Optional[int]
    categories: dict[str, CategorySummary]


class SnapshotTriggerIn(Schema):
    force: bool = False
    webhook_url: Optional[str] = None


class SnapshotTriggerOut(Schema):
    id: int
    status: str
    existing: bool
    poll_url: str
    webhook_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


class PageCategorySummary(Schema):
    score: int
    rating: str


class PageListOut(Schema):
    id: int
    url: str
    audited: bool
    html_report_url: Optional[str]
    categories: dict[str, PageCategorySummary]


class AuditDetailOut(Schema):
    title: str
    description: str
    category: str
    score: Optional[int]
    rating: Optional[str]
    value: Optional[float]
    units: Optional[str]
    details: Optional[Any]


class PageDetailOut(Schema):
    id: int
    url: str
    audited: bool
    html_report_url: Optional[str]
    categories: dict[str, PageCategorySummary]
    audits: dict[str, AuditDetailOut]


# ---------------------------------------------------------------------------
# Audit definitions
# ---------------------------------------------------------------------------


class AuditDefinitionOut(Schema):
    audit_id: str
    category_id: str
    title: str
    description: str
    weight: float


class AuditDefinitionWithStats(Schema):
    audit_id: str
    category_id: str
    title: str
    description: str
    weight: float
    fail_rate: Optional[float] = None
    failing_pages: Optional[int] = None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class JobOut(Schema):
    id: int
    kind: str
    status: str
    started: datetime
    duration_s: Optional[int]
    retry_after: Optional[int]
    result_url: Optional[str]


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class FeedbackIn(Schema):
    message: str
    endpoint: str = ""


class FeedbackOut(Schema):
    id: int
    endpoint: str
    message: str
    created: datetime


# ---------------------------------------------------------------------------
# Paginated wrapper
# ---------------------------------------------------------------------------


class PaginatedOut(Schema):
    items: list[Any]
    count: int
    limit: int
    truncated: bool
    next_cursor: Optional[str]
    hint: str
