from django.contrib import admin
from django.contrib.admin import register
from django.utils.translation import gettext_lazy as _

from ..models import Job
from ..tasks import job_run


@register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("name", "site", "device", "enabled")
    list_filters = ("site", "device")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created", "modified")
    actions = ["run_selected_jobs"]

    @admin.action(description="Run selected jobs")
    def run_selected_jobs(self, request, queryset):
        for job in queryset:
            job_run.delay(job.pk)
            self.message_user(request, _("Run triggered for %(job)s") % {"job": job})
