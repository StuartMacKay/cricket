import base64
import json
from typing import Generic, Optional, TypeVar

from ninja import Schema

T = TypeVar("T")

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def encode_cursor(pk: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"id": pk}).encode()).decode()


def decode_cursor(cursor: str) -> Optional[int]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return data.get("id")
    except Exception:
        return None


def paginate(queryset, limit: int, cursor: Optional[str] = None, hint: str = ""):
    """Apply cursor pagination to a queryset ordered by pk descending."""
    limit = min(max(1, limit), MAX_LIMIT)

    if cursor:
        cursor_pk = decode_cursor(cursor)
        if cursor_pk is not None:
            queryset = queryset.filter(pk__lt=cursor_pk)

    items = list(queryset[:limit + 1])
    truncated = len(items) > limit
    if truncated:
        items = items[:limit]

    next_cursor = None
    if truncated and items:
        next_cursor = encode_cursor(items[-1].pk)

    return {
        "items": items,
        "count": len(items),
        "limit": limit,
        "truncated": truncated,
        "next_cursor": next_cursor,
        "hint": hint,
    }
