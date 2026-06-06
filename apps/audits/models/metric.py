from django.db import models
from django.utils.translation import gettext_lazy as _


class Rating(models.TextChoices):
    POOR = "poor", _("Poor")
    NEEDS_IMPROVEMENT = "needs-improvement", _("Needs Improvement")
    GOOD = "good", _("Good")

    @classmethod
    def get_rating(cls, score: int | None) -> str | None:
        """Map a 0-100 score to a rating string.

        Returns None when score is None (audit not applicable).
        """
        if score is None:
            return None
        if score >= 90:
            return cls.GOOD
        if score >= 50:
            return cls.NEEDS_IMPROVEMENT
        return cls.POOR


class Metric(models.Model):
    """A single extracted scalar from a Report, described by a Definition.

    After an audit task creates a Report, it extracts one Metric per Definition
    the audit supports. Metrics hold the normalised scalar (value + units),
    an optional 0-100 score, and a three-band rating (poor/needs-improvement/
    good). Storing Metrics separately from the raw Report JSONField allows
    efficient querying and trend analysis without parsing raw tool output.

    page and measured are denormalised shortcuts: page is also reachable via
    report.page, and measured mirrors run.created at the time of writing.
    Both are immutable after creation and exist solely to avoid joining through
    Report for common analytical queries such as time-series graphs.
    """

    class Meta:
        verbose_name = _("Metric")
        verbose_name_plural = _("Metrics")
        indexes = [
            models.Index(
                fields=["definition", "rating"],
                name="ck_metric_defn_rating_idx",
            ),
            models.Index(
                fields=["page", "definition", "measured"],
                name="ck_metric_pg_defn_time_idx",
            ),
        ]

    page = models.ForeignKey(
        "Page",
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name=_("Page"),
        help_text=_("The Page this Metric was measured for."),
    )

    measured = models.DateTimeField(
        db_index=True,
        verbose_name=_("Measured"),
        help_text=_("When the audit ran. Mirrors the Run's created timestamp."),
    )

    report = models.ForeignKey(
        "Report",
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name=_("Report"),
        help_text=_("The Report from which this Metric was extracted."),
    )

    definition = models.ForeignKey(
        "Definition",
        on_delete=models.CASCADE,
        related_name="metrics",
        verbose_name=_("Definition"),
        help_text=_("The Definition that describes this Metric."),
    )

    score = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Score"),
        help_text=_("The score for the metric."),
    )

    rating = models.CharField(
        max_length=20,
        choices=Rating.choices,
        null=True,
        blank=True,
        verbose_name=_("Rating"),
        help_text=_("A rating for the metric."),
    )

    value = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Value"),
        help_text=_("The actual value."),
    )

    units = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Units"),
        help_text=_("The units for the value, e.g. milliseconds, bytes, etc."),
    )

    data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Data"),
        help_text=_("The raw audit data used to generate this Metric."),
    )

    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("The date and time the record was added."),
    )

    def __str__(self):
        return f"{self.report} - {self.definition}: {self.rating}"
