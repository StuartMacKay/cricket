from django.contrib import admin

from ..models import PageHeaders


@admin.register(PageHeaders)
class PageHeadersAdmin(admin.ModelAdmin):
    list_display = ("url", "status_code", "redirect_count", "snapshot")
    list_filter = ("status_code",)
    ordering = ("-created",)
    search_fields = ("url",)
    readonly_fields = (
        "snapshot",
        "url",
        "final_url",
        "status_code",
        "redirect_count",
        "headers",
        "error",
        "created",
        "modified",
    )

    def has_add_permission(self, request, obj=None):
        return False
