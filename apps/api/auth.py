from typing import Optional

from django.utils import timezone
from ninja.security import HttpBearer

from .models import APIKey


class BearerAuth(HttpBearer):
    """Validate Authorization: Bearer <key> header against APIKey rows."""

    def authenticate(self, request, token: str) -> Optional[APIKey]:
        try:
            key = APIKey.objects.select_related("site").get(key=token)
        except APIKey.DoesNotExist:
            return None
        APIKey.objects.filter(pk=key.pk).update(last_used=timezone.now())
        return key


bearer_auth = BearerAuth()
