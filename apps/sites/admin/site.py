from django.contrib import admin
from django.contrib.admin import register
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_json_widget.widgets import JSONEditorWidget

from ..models import Site
from ..tasks import take_site_snapshot


@register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "enabled", "platform", "snapped")
    list_filter = ("enabled", "platform")
    ordering = ("-created",)
    search_fields = ("name", "url")
    readonly_fields = ("created", "modified", "snapped", "current_snapshot")
    actions = ["trigger_snapshot"]

    formfield_overrides = {
        models.JSONField: {"widget": JSONEditorWidget},
    }

    def trigger_snapshot(self, request, queryset):
        for site in queryset:
            take_site_snapshot.delay(site.pk)
            self.message_user(
                request,
                _("Snapshot queued for %(name)s") % {"name": site.name},
            )

    trigger_snapshot.short_description = "Trigger snapshot for selected sites"
