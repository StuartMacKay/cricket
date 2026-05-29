from django.contrib import admin
from .models import APIFeedback, APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key_truncated", "site", "is_admin", "last_used", "created")
    readonly_fields = ("key", "last_used", "created", "modified")
    list_filter = ("is_admin",)
    search_fields = ("name",)
    fields = ("name", "key", "site", "is_admin", "last_used", "created", "modified")

    @admin.display(description="Key")
    def key_truncated(self, obj):
        return f"{obj.key[:8]}…"


@admin.register(APIFeedback)
class APIFeedbackAdmin(admin.ModelAdmin):
    list_display = ("api_key", "endpoint", "created")
    readonly_fields = ("api_key", "endpoint", "message", "created", "modified")
    ordering = ("-created",)

    def has_add_permission(self, request):
        return False
