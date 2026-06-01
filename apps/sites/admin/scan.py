from django.contrib import admin
from django.contrib.admin import register

from ..models import Page, Scan


@register(Scan)
class ScanAdmin(admin.ModelAdmin):
    list_display = ("site", "platform", "environment", "status", "created")
    list_filter = ("status", "platform", "environment")
    ordering = ("-created",)
    search_fields = ("site__name",)
    readonly_fields = ("site", "platform", "environment", "status", "webhook_url", "created", "modified")

    def has_add_permission(self, request):
        return False


@register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("url", "scan")
    ordering = ("url",)
    search_fields = ("url",)
    readonly_fields = ("scan", "url", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
