from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Audit(models.Model):
    """A named audit type provided by a tool, backed by a Celery task.

    Audits are registered via data migrations when a tool is installed.
    Each record maps a human-readable name to the Celery task that runs the
    audit and produces a Report for a given page.
    """

    class Meta:
        verbose_name = _("Audit")
        verbose_name_plural = _("Audits")

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name"),
        help_text=_("The name of the Audit.")
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("The slug used to refer to the Audit in API URLs."),
    )

    task = models.CharField(
        max_length=255,
        verbose_name=_("Task"),
        help_text=_("The module path of the Celery task that performs the audit.")
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("An agent-friendly description of the Audit.")
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
