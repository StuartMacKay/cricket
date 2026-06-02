from django.db import models
from django.utils.translation import gettext_lazy as _

from sites.models.base_job import BaseJob


class Job(BaseJob):
    TASK_NAME = "pageweight.tasks.take_weight_run"

    class Meta:
        verbose_name = _("Page Weight Job")
        verbose_name_plural = _("Page Weight Jobs")

    class Device(models.TextChoices):
        MOBILE  = "mobile",  _("Mobile")
        DESKTOP = "desktop", _("Desktop")

    device = models.CharField(
        max_length=10,
        choices=Device.choices,
        default=Device.MOBILE,
        verbose_name=_("Device"),
    )

    def __str__(self):
        return f"{self.site.name} — Page weight ({self.device})"
