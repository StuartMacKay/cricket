from django.contrib import admin

from ..models import Page, Resource


class ResourceInline(admin.TabularInline):
    model         = Resource
    fields        = ("resource_type", "url", "transfer_size", "resource_size", "mime_type")
    readonly_fields = fields
    extra = 0; max_num = 0; ordering = ("-transfer_size",)

    def has_add_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display    = ("url", "run", "measured", "total_transfer_size", "resource_count")
    list_filter     = ("measured",)
    ordering        = ("-total_transfer_size",)
    search_fields   = ("url",)
    readonly_fields = (
        "run", "url", "final_url", "measured", "error",
        "total_transfer_size", "total_resource_size", "resource_count",
        "document_transfer", "stylesheet_transfer", "script_transfer",
        "image_transfer", "font_transfer", "other_transfer",
        "document_size", "stylesheet_size", "script_size",
        "image_size", "font_size", "other_size",
        "created", "modified",
    )
    inlines = [ResourceInline]

    def has_add_permission(self, request, obj=None):    return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser
