from django.db import models
from django.utils.translation import gettext_lazy as _

from .rating import Rating


class AuditDefinition(models.Model):
    class Meta:
        verbose_name = _("Audit Definition")
        verbose_name_plural = _("Audit Definitions")
        ordering = ["category_id", "audit_id"]

    audit_id = models.CharField(
        primary_key=True, max_length=100,
        verbose_name=_("Audit ID"),
    )
    category_id = models.CharField(max_length=50, db_index=True, verbose_name=_("Category ID"))
    title       = models.CharField(max_length=255, verbose_name=_("Title"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    weight      = models.FloatField(default=0, verbose_name=_("Weight"))

    def __str__(self):
        return f"{self.audit_id} ({self.category_id})"


class PageCategory(models.Model):
    class Meta:
        verbose_name = _("Page Category")
        verbose_name_plural = _("Page Categories")
        unique_together = [("page", "category_id")]
        indexes = [
            models.Index(fields=["category_id", "score"],  name="lh_pagecat_cat_score_idx"),
            models.Index(fields=["category_id", "rating"], name="lh_pagecat_cat_rating_idx"),
        ]

    page = models.ForeignKey(
        "lighthouse.Page",
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name=_("Page"),
    )
    category_id = models.CharField(max_length=50, verbose_name=_("Category ID"))
    title       = models.CharField(max_length=100, verbose_name=_("Title"))
    score       = models.IntegerField(verbose_name=_("Score"))
    rating      = models.CharField(max_length=20, choices=Rating.CHOICES, verbose_name=_("Rating"))

    def __str__(self):
        return f"{self.page} — {self.category_id}: {self.score}"


class PageAudit(models.Model):
    class Meta:
        verbose_name = _("Page Audit")
        verbose_name_plural = _("Page Audits")
        unique_together = [("page", "audit")]
        indexes = [
            models.Index(fields=["audit", "rating"], name="lh_pageaudit_audit_rating_idx"),
        ]

    page = models.ForeignKey(
        "lighthouse.Page",
        on_delete=models.CASCADE,
        related_name="audits",
        verbose_name=_("Page"),
    )
    audit = models.ForeignKey(
        AuditDefinition,
        on_delete=models.CASCADE,
        related_name="page_audits",
        verbose_name=_("Audit"),
    )
    score   = models.IntegerField(null=True, blank=True, verbose_name=_("Score"))
    rating  = models.CharField(max_length=20, choices=Rating.CHOICES, null=True, blank=True, verbose_name=_("Rating"))
    value   = models.FloatField(null=True, blank=True, verbose_name=_("Value"))
    units   = models.CharField(max_length=50, blank=True, verbose_name=_("Units"))
    details = models.JSONField(null=True, blank=True, verbose_name=_("Details"))

    def __str__(self):
        return f"{self.page} — {self.audit_id}: {self.rating}"
