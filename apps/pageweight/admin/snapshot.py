from django.contrib import admin

from ..models import WeightSnapshot
from ..tasks import take_weight_snapshot


@admin.register(WeightSnapshot)
class WeightSnapshotAdmin(admin.ModelAdmin):
    list_display = ("site", "platform", "status", "page_count", "created")
    list_filter = ("status", "platform")
    ordering = ("-created",)
    search_fields = ("site__name",)
    readonly_fields = ("site", "platform", "status", "page_count", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False
