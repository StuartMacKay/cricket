from django.contrib import admin, messages
from django.contrib.admin import register
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_json_widget.widgets import JSONEditorWidget

from ..models import Site
from ..tasks import take_snapshot


@register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "url", "enabled")
    ordering = ("-created",)
    search_fields = ("name", "url")
    readonly_fields = ("created", "modified")
    actions = ["create_snapshot"]

    formfield_overrides = {
        models.JSONField: {"widget": JSONEditorWidget},
    }

    def create_snapshot(self, request, queryset):
        for site in queryset:
            take_snapshot.delay(site.pk)
            messages.info(
                request,
                _("Creating snapshot of %(name)s") % {"name": site.name},
            )

    create_snapshot.short_description = "Create Snapshot of selected Sites"
