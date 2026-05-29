from django.contrib import admin
from .models import APIFeedback, APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("name", "key_prefix", "site", "is_admin", "last_used", "created")
    readonly_fields = ("key_prefix", "hashed_key", "last_used", "created", "modified")
    list_filter = ("is_admin",)
    search_fields = ("name",)

    def has_change_permission(self, request, obj=None):
        # Keys cannot be changed — only created or deleted
        return False


@admin.register(APIFeedback)
class APIFeedbackAdmin(admin.ModelAdmin):
    list_display = ("api_key", "endpoint", "created")
    readonly_fields = ("api_key", "endpoint", "message", "created", "modified")
    ordering = ("-created",)

    def has_add_permission(self, request):
        return False
