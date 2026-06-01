from django.contrib import admin
from django.contrib.admin import register
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_json_widget.widgets import JSONEditorWidget

from ..models import Site
from ..tasks import take_site_scan


@register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "enabled", "platform", "snapped")
    list_filter = ("enabled", "platform")
    ordering = ("-created",)
    search_fields = ("name", "url")
    readonly_fields = ("created", "modified", "snapped", "current_scan")
    actions = ["trigger_scan"]

    formfield_overrides = {
        models.JSONField: {"widget": JSONEditorWidget},
    }

    def trigger_scan(self, request, queryset):
        for site in queryset:
            take_site_scan.delay(site.pk)
            self.message_user(
                request,
                _("Scan queued for %(name)s") % {"name": site.name},
            )

    trigger_scan.short_description = "Trigger scan for selected sites"
