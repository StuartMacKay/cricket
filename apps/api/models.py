import secrets

from django.db import models
from django.utils.translation import gettext_lazy as _

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from django_extensions.db.models import TimeStampedModel

_ph = PasswordHasher()


def _generate_key():
    return secrets.token_urlsafe(32)


class APIKey(TimeStampedModel, models.Model):
    """Named API key for agent authentication.

    The full plaintext key is only shown at creation time.  Only the
    argon2 hash and the first 8 characters (prefix) are stored.
    """

    class Meta:
        verbose_name = _("API Key")
        verbose_name_plural = _("API Keys")

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Name"),
        help_text=_("Human-readable name shown in agent-context responses"),
    )

    key_prefix = models.CharField(
        max_length=8,
        verbose_name=_("Key prefix"),
        help_text=_("First 8 characters of the key, shown in admin for identification"),
    )

    hashed_key = models.CharField(
        max_length=200,
        verbose_name=_("Hashed key"),
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
        return f"{self.name} ({self.key_prefix}…)"

    @classmethod
    def create(cls, name: str, site=None, is_admin: bool = False) -> tuple["APIKey", str]:
        """Create a new APIKey and return (instance, plaintext_key).

        The plaintext key is returned only once and never stored.
        """
        plaintext = _generate_key()
        prefix = plaintext[:8]
        hashed = _ph.hash(plaintext)
        key = cls.objects.create(
            name=name,
            key_prefix=prefix,
            hashed_key=hashed,
            site=site,
            is_admin=is_admin,
        )
        return key, plaintext

    def verify(self, plaintext: str) -> bool:
        try:
            return _ph.verify(self.hashed_key, plaintext)
        except VerifyMismatchError:
            return False


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
