from datetime import datetime
from typing import Any, Optional

from ninja import Schema


class SiteOut(Schema):
    slug:        str
    name:        str
    primary_url: str
    description: str


class AuditDefinitionOut(Schema):
    audit_id:    str
    category_id: str
    title:       str
    description: str
    weight:      float


class AuditDefinitionWithStats(Schema):
    audit_id:      str
    category_id:   str
    title:         str
    description:   str
    weight:        float
    fail_rate:     Optional[float] = None
    failing_pages: Optional[int]   = None


class FeedbackIn(Schema):
    message:  str
    endpoint: str = ""


class FeedbackOut(Schema):
    id:       int
    endpoint: str
    message:  str
    created:  datetime


class PaginatedOut(Schema):
    items:       list[Any]
    count:       int
    limit:       int
    truncated:   bool
    next_cursor: Optional[str]
    hint:        str
