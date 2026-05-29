from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from ..models import HeaderSnapshot
from ..tasks import take_header_snapshot


@admin.register(HeaderSnapshot)
class HeaderSnapshotAdmin(admin.ModelAdmin):
    list_display = ("site", "status", "page_count", "created")
    list_filter = ("status",)
    ordering = ("-created",)
    search_fields = ("site__name",)
    readonly_fields = ("site", "status", "page_count", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False
