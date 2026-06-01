from django.contrib import admin

from ..models import Run


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "page_count", "created")
    ordering = ("-created",)
    search_fields = ("scan__site__name",)
    list_filter = ("status",)
    readonly_fields = (
        "scan",
        "status",
        "page_count",
        "config_file",
        "created",
        "modified",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
