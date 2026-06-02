from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from django_extensions.db.models import TimeStampedModel


class Site(TimeStampedModel, models.Model):
    """Stable identity record — the name agents and humans use to group results.

    Configuration (which URLs, which tools, schedules) lives in per-tool
    Job models. Site is identity only.
    """

    class Meta:
        verbose_name = _("Site")
        verbose_name_plural = _("Sites")

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name"),
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("Used in API URLs. Auto-generated from name if left blank."),
    )

    primary_url = models.URLField(
        verbose_name=_("Primary URL"),
        help_text=_("The site's main URL, for display purposes."),
    )

    description = models.TextField(blank=True, verbose_name=_("Description"))

    def __str__(self):
        return self.name

    def save(self, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(**kwargs)
