from django.db import models
from django.utils.translation import gettext_lazy as _

from sites.models.base_job import BaseJob


class Job(BaseJob):
    TASK_NAME = "lighthouse.tasks.take_lighthouse_run"

    class Meta:
        verbose_name = _("Lighthouse Job")
        verbose_name_plural = _("Lighthouse Jobs")

    class Platform(models.TextChoices):
        MOBILE  = "mobile",  _("Mobile")
        DESKTOP = "desktop", _("Desktop")

    platform = models.CharField(
        max_length=10,
        choices=Platform.choices,
        default=Platform.MOBILE,
        verbose_name=_("Platform"),
    )

    cat_performance    = models.BooleanField(default=True, verbose_name=_("Performance"))
    cat_accessibility  = models.BooleanField(default=True, verbose_name=_("Accessibility"))
    cat_best_practices = models.BooleanField(default=True, verbose_name=_("Best practices"))
    cat_seo            = models.BooleanField(default=True, verbose_name=_("SEO"))

    def get_only_categories(self) -> list[str] | None:
        """Return the list of enabled categories, or None if all four are on.

        None means no --only-categories flag is passed to Lighthouse, which
        is equivalent to running all categories and slightly more efficient.
        """
        mapping = {
            "performance":   self.cat_performance,
            "accessibility": self.cat_accessibility,
            "best-practices": self.cat_best_practices,
            "seo":           self.cat_seo,
        }
        enabled = [k for k, v in mapping.items() if v]
        return None if len(enabled) == 4 else enabled

    def __str__(self):
        cats = self.get_only_categories()
        label = ", ".join(cats) if cats else "all categories"
        return f"{self.site.name} — Lighthouse ({label})"
