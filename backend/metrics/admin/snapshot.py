from django.contrib import admin

from ..models import Snapshot


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("site", "created")
    ordering = ("-created",)
    search_fields = ("site",)
    readonly_fields = (
        "site",
        "data",
        "created",
        "modified",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
