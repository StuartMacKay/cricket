from typing import Optional

from django.utils import timezone
from ninja.security import HttpBearer

from .models import APIKey


class BearerAuth(HttpBearer):
    """Validate Authorization: Bearer <key> header against hashed APIKey rows."""

    def authenticate(self, request, token: str) -> Optional[APIKey]:
        prefix = token[:8]
        candidates = APIKey.objects.filter(key_prefix=prefix).select_related("site")
        for candidate in candidates:
            if candidate.verify(token):
                APIKey.objects.filter(pk=candidate.pk).update(last_used=timezone.now())
                return candidate
        return None


bearer_auth = BearerAuth()
