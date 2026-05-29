from django.contrib import admin

from ..models import Page, Resource


class ResourceInline(admin.TabularInline):
    model = Resource
    fields = ("resource_type", "url", "transfer_size", "resource_size", "mime_type")
    readonly_fields = fields
    extra = 0
    max_num = 0
    ordering = ("-transfer_size",)
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = (
        "url",
        "snapshot",
        "measured",
        "total_transfer_size",
        "total_resource_size",
        "resource_count",
    )
    list_filter = ("measured",)
    ordering = ("-total_transfer_size",)
    search_fields = ("url",)
    readonly_fields = (
        "snapshot",
        "url",
        "final_url",
        "measured",
        "total_transfer_size",
        "total_resource_size",
        "resource_count",
        "error",
        "created",
        "modified",
    )
    inlines = [ResourceInline]

    def has_add_permission(self, request, obj=None):
        return False
