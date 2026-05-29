from django.contrib import admin

from ..models import Snapshot


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("site", "status", "platform", "page_count", "created")
    ordering = ("-created",)
    search_fields = ("site__name",)
    list_filter = ("status", "platform")
    readonly_fields = (
        "site",
        "status",
        "platform",
        "page_count",
        "created",
        "modified",
    )

    def has_add_permission(self, request, obj=None):
        return False
