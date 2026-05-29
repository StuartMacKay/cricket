from django.contrib import admin

from ..models import Snapshot


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("__str__", "platform", "status", "page_count", "created")
    list_filter = ("status",)
    ordering = ("-created",)
    search_fields = ("snapshot__site__name",)
    readonly_fields = ("snapshot", "platform", "status", "page_count", "created", "modified")

    @admin.display(description="Platform")
    def platform(self, obj):
        return obj.snapshot.platform

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
