from django.utils.translation import gettext_lazy as _

from sites.models.base_job import BaseJob


class Job(BaseJob):
    TASK_NAME = "headers.tasks.take_header_run"

    class Meta:
        verbose_name = _("Headers Job")
        verbose_name_plural = _("Headers Jobs")

    def __str__(self):
        return f"{self.site.name} — Headers"
