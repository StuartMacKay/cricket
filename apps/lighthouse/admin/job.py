from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from ..models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display  = ("site", "platform", "environment", "crontab", "enabled", "last_run")
    list_filter   = ("enabled", "platform", "environment")
    search_fields = ("site__name",)
    ordering      = ("site__name",)
    readonly_fields = ("created", "modified", "last_run")
    actions       = ["trigger_run"]

    fieldsets = (
        (None, {"fields": ("site", "enabled")}),
        (_("URL source"), {"fields": ("url_source", "url_value", "sitemap_file")}),
        (_("Schedule"), {"fields": ("crontab", "last_run")}),
        (_("Configuration"), {"fields": ("platform", "environment")}),
        (_("Categories"), {"fields": ("cat_performance", "cat_accessibility", "cat_best_practices", "cat_seo")}),
        (_("Metadata"), {"fields": ("created", "modified")}),
    )

    def trigger_run(self, request, queryset):
        for job in queryset:
            job.trigger_run()
            self.message_user(request, _("Run triggered for %(job)s") % {"job": job})

    trigger_run.short_description = _("Trigger run now")
