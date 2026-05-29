from django.contrib import admin

from ..models import Snapshot


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "page_count", "created")
    list_filter = ("status",)
    ordering = ("-created",)
    search_fields = ("snapshot__site__name",)
    readonly_fields = ("snapshot", "status", "page_count", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False
