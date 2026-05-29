from django.contrib import admin
from django.contrib.admin import register

from ..models import Snapshot


@register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("site", "platform", "status", "created")
    list_filter = ("status", "platform")
    ordering = ("-created",)
    search_fields = ("site__name",)
    readonly_fields = ("site", "platform", "status", "webhook_url", "created", "modified")

    def has_add_permission(self, request):
        return False
