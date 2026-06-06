from django.contrib import admin

from .models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display  = ("name", "key_truncated", "site", "last_used", "created")
    readonly_fields = ("key", "last_used", "created")
    search_fields = ("name",)
    fields = ("name", "key", "site", "last_used", "created")

    @admin.display(description="Key")
    def key_truncated(self, obj):
        return f"{obj.key[:8]}…"
