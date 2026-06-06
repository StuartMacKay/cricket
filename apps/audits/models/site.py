from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Site(models.Model):
    """A web site on which audits are run.

    Site is an identity record — it groups Jobs, Pages, and their audit
    history under a stable name. Separate Site records should be used for
    different environments (local, staging, production) of the same project
    so that results from different environments are not mixed when comparing
    metrics over time.
    """

    class Meta:
        verbose_name = _("Site")
        verbose_name_plural = _("Sites")

    class Environment(models.TextChoices):
        LOCAL = "local", _("Local")
        STAGING = "staging", _("Staging")
        PRODUCTION = "production", _("Production")

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name"),
        help_text=_("The name of the site.")
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("Used in API URLs. Auto-generated from name if left blank."),
    )

    url = models.URLField(
        verbose_name=_("URL"),
        help_text=_("The site's main URL."),
    )

    environment = models.CharField(
        max_length=20,
        blank=True,
        choices=Environment.choices,
        verbose_name=_("Environment"),
        help_text=_("The type of server environment. Used for filtering job runs."),
    )

    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("The date and time the record was added."),
    )

    modified = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Modified at"),
        help_text=_("The date and time the record was last modified."),
    )

    def __str__(self):
        return self.name

    def save(self, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(**kwargs)
