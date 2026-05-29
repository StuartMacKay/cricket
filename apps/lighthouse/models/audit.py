from django.db import models
from django.utils.translation import gettext_lazy as _

from .rating import Rating


class AuditDefinition(models.Model):
    """Lookup table populated from the Lighthouse report on each audit run.

    Contains ~150 rows (one per distinct Lighthouse audit).  Upserted each
    time a page is audited so that title/description always reflect the
    version of Lighthouse that was used for the most recent run.
    """

    class Meta:
        verbose_name = _("Audit Definition")
        verbose_name_plural = _("Audit Definitions")
        ordering = ["category_id", "audit_id"]

    audit_id = models.CharField(
        primary_key=True,
        max_length=100,
        verbose_name=_("Audit ID"),
        help_text=_("The Lighthouse audit identifier, e.g. 'first-contentful-paint'"),
    )

    category_id = models.CharField(
        max_length=50,
        verbose_name=_("Category ID"),
        help_text=_("The primary category this audit belongs to"),
        db_index=True,
    )

    title = models.CharField(
        max_length=255,
        verbose_name=_("Title"),
    )

    description = models.TextField(
        verbose_name=_("Description"),
        blank=True,
    )

    weight = models.FloatField(
        default=0,
        verbose_name=_("Weight"),
        help_text=_("Weight of this audit within its category (0 for binary audits)"),
    )

    def __str__(self):
        return f"{self.audit_id} ({self.category_id})"


class PageCategory(models.Model):
    """Lighthouse category score for a single audited page."""

    class Meta:
        verbose_name = _("Page Category")
        verbose_name_plural = _("Page Categories")
        unique_together = [("page", "category_id")]
        indexes = [
            models.Index(fields=["category_id", "score"]),
            models.Index(fields=["category_id", "rating"]),
        ]

    page = models.ForeignKey(
        "Page",
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name=_("Page"),
    )

    category_id = models.CharField(
        max_length=50,
        verbose_name=_("Category ID"),
    )

    title = models.CharField(
        max_length=100,
        verbose_name=_("Title"),
    )

    score = models.IntegerField(
        verbose_name=_("Score"),
        help_text=_("0–100 score for this category"),
    )

    rating = models.CharField(
        max_length=20,
        choices=Rating.CHOICES,
        verbose_name=_("Rating"),
    )

    def __str__(self):
        return f"{self.page} — {self.category_id}: {self.score}"


class PageAudit(models.Model):
    """Lighthouse audit result for a single audited page."""

    class Meta:
        verbose_name = _("Page Audit")
        verbose_name_plural = _("Page Audits")
        unique_together = [("page", "audit")]
        indexes = [
            models.Index(fields=["audit", "rating"]),
        ]

    page = models.ForeignKey(
        "Page",
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

    score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Score"),
        help_text=_("0–100 score, or null when not applicable"),
    )

    rating = models.CharField(
        max_length=20,
        choices=Rating.CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Rating"),
    )

    # Numeric audits only
    value = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Value"),
        help_text=_("Numeric value (e.g. milliseconds for timing audits)"),
    )

    units = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Units"),
    )

    # Failing items from the audit details section
    details = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Details"),
        help_text=_("Failing items from the audit details section"),
    )

    def __str__(self):
        return f"{self.page} — {self.audit_id}: {self.rating}"


class SnapshotCategory(models.Model):
    """Aggregated category results across all pages in a snapshot."""

    class Meta:
        verbose_name = _("Snapshot Category")
        verbose_name_plural = _("Snapshot Categories")
        unique_together = [("snapshot", "category_id")]
        ordering = ["category_id"]

    snapshot = models.ForeignKey(
        "Snapshot",
        on_delete=models.CASCADE,
        related_name="category_results",
        verbose_name=_("Snapshot"),
    )

    category_id = models.CharField(
        max_length=50,
        verbose_name=_("Category ID"),
    )

    title = models.CharField(
        max_length=100,
        verbose_name=_("Title"),
    )

    poor_count = models.IntegerField(default=0, verbose_name=_("Poor count"))
    needs_count = models.IntegerField(default=0, verbose_name=_("Needs Improvement count"))
    good_count = models.IntegerField(default=0, verbose_name=_("Good count"))

    score_avg = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Average score"),
    )

    def __str__(self):
        return f"{self.snapshot} — {self.category_id}"

    @property
    def total(self):
        return self.poor_count + self.needs_count + self.good_count


class SnapshotAudit(models.Model):
    """Aggregated audit results across all pages in a snapshot."""

    class Meta:
        verbose_name = _("Snapshot Audit")
        verbose_name_plural = _("Snapshot Audits")
        unique_together = [("snapshot", "audit")]
        ordering = ["audit__category_id", "audit__audit_id"]

    snapshot = models.ForeignKey(
        "Snapshot",
        on_delete=models.CASCADE,
        related_name="audit_results",
        verbose_name=_("Snapshot"),
    )

    audit = models.ForeignKey(
        AuditDefinition,
        on_delete=models.CASCADE,
        related_name="snapshot_audits",
        verbose_name=_("Audit"),
    )

    poor_count = models.IntegerField(default=0, verbose_name=_("Poor count"))
    needs_count = models.IntegerField(default=0, verbose_name=_("Needs Improvement count"))
    good_count = models.IntegerField(default=0, verbose_name=_("Good count"))

    def __str__(self):
        return f"{self.snapshot} — {self.audit_id}"

    @property
    def total(self):
        return self.poor_count + self.needs_count + self.good_count
