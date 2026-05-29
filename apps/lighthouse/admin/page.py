from django.contrib import admin

from ..models import Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("url", "snapshot", "audited", "created")
    ordering = ("-created",)
    search_fields = ("url",)
    list_filter = ("audited",)
    readonly_fields = (
        "url",
        "report",
        "html_report",
        "snapshot",
        "audited",
        "created",
        "modified",
    )

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
