import secrets

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def _generate_key():
    return secrets.token_urlsafe(32)


class APIKey(models.Model):
    """Named API key for authenticating requests to the api endpoints."""

    class Meta:
        verbose_name = _("API Key")
        verbose_name_plural = _("API Keys")

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Name"),
        help_text=_("Human-readable label for this key."),
    )

    key = models.CharField(
        max_length=64,
        unique=True,
        default=_generate_key,
        verbose_name=_("Key"),
    )

    site = models.ForeignKey(
        "audits.Site",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_keys",
        verbose_name=_("Site scope"),
        help_text=_("Limit this key to a single site; leave blank for all sites."),
    )

    last_used = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last used"),
    )

    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
