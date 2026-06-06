from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Run(models.Model):
    """A single execution of a Job, grouping all Reports generated at that time.

    A Run is created by the execute_run task when a Job fires. It tracks
    overall status across the parallel audit tasks and records the number of
    distinct pages audited once complete. All Reports produced during this
    execution reference this Run, making it the anchor for a point-in-time
    snapshot of the site's audit results.
    """

    class Meta:
        verbose_name = _("Run")
        verbose_name_plural = _("Runs")
        ordering = ["-created"]

    class Status(models.TextChoices):
        RUNNING  = "running",  _("Running")
        COMPLETE = "complete", _("Complete")
        FAILED   = "failed",   _("Failed")

    job = models.ForeignKey(
        "Job",
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name=_("Job"),
        help_text=_("The Job that generated this Run.")
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
        verbose_name=_("Status"),
        help_text=_("The current status of this Run.")
    )

    page_count = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Page count"),
        help_text=_("The number of pages audited.")
    )

    total_tasks = models.IntegerField(
        default=0,
        verbose_name=_("Total tasks"),
        help_text=_("The number of audit-page tasks dispatched for this Run.")
    )

    completed_tasks = models.IntegerField(
        default=0,
        verbose_name=_("Completed tasks"),
        help_text=_("The number of audit-page tasks that have finished.")
    )

    created = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
        help_text=_("The date and time the record was added."),
    )

    def __str__(self):
        return f"{self.job.site.name} ({self.created.strftime('%Y-%m-%d')})"

    def complete(self):
        self.page_count = self.reports.values("page").distinct().count()
        self.status = Run.Status.COMPLETE
        self.save(update_fields=["page_count", "status"])
        self.job.executed = timezone.now()
        self.job.save(update_fields=["executed"])

    def task_complete(self):
        """Increment completed_tasks; mark Run complete when all tasks are done."""
        with transaction.atomic():
            run = Run.objects.select_for_update().get(pk=self.pk)
            run.completed_tasks += 1
            run.save(update_fields=["completed_tasks"])
            if run.completed_tasks >= run.total_tasks:
                run.complete()
