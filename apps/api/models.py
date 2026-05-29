import secrets

from django.db import models
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel


def _generate_key():
    return secrets.token_urlsafe(32)


class APIKey(TimeStampedModel, models.Model):
    """Named API key for agent authentication."""

    class Meta:
        verbose_name = _("API Key")
        verbose_name_plural = _("API Keys")

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Name"),
        help_text=_("Human-readable name shown in agent-context responses"),
    )

    key = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_("Key"),
        default=_generate_key,
    )

    site = models.ForeignKey(
        "sites.Site",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_keys",
        verbose_name=_("Site scope"),
        help_text=_("Limit this key to a single site; leave blank for all sites"),
    )

    is_admin = models.BooleanField(
        default=False,
        verbose_name=_("Admin key"),
        help_text=_("Admin keys can read feedback and manage other resources"),
    )

    last_used = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last used"),
    )

    def __str__(self):
        return self.name


class APIFeedback(TimeStampedModel, models.Model):
    """Friction report submitted by an agent."""

    class Meta:
        verbose_name = _("API Feedback")
        verbose_name_plural = _("API Feedback")
        ordering = ["-created"]

    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedback",
        verbose_name=_("API Key"),
    )

    endpoint = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Endpoint"),
        help_text=_("The endpoint that caused friction"),
    )

    message = models.TextField(
        verbose_name=_("Message"),
    )

    def __str__(self):
        return f"Feedback from {self.api_key} at {self.created}"
