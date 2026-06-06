from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class Definition(models.Model):
    """Describes a named, measurable quantity produced by an Audit.

    Definitions are registered alongside their Audit via data migrations.
    Each Definition belongs to one Audit and describes a scalar that the audit
    extracts — e.g. largest-contentful-paint for a Lighthouse audit, or
    total-transfer-size for a page weight audit.
    """

    class Meta:
        verbose_name = _("Definition")
        verbose_name_plural = _("Definitions")

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name"),
        help_text=_("The name of the Definition."),
    )

    slug = models.SlugField(
        max_length=100,
        unique=True,
        verbose_name=_("Slug"),
        help_text=_("The slug used to refer to the Definition in API URLs."),
    )

    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("An agent-friendly description of the Definition."),
    )

    weight = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Weight"),
        help_text=_("How much does the metric influence the overall score of the audit."),
    )

    audit = models.ForeignKey(
        "Audit",
        on_delete=models.CASCADE,
        related_name="definitions",
        verbose_name=_("Audit"),
        help_text=_("The Audit that produces this Definition."),
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
