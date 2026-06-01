from django.contrib import admin

from ..models import AuditDefinition


@admin.register(AuditDefinition)
class AuditDefinitionAdmin(admin.ModelAdmin):
    list_display = ("audit_id", "category_id", "title", "weight")
    list_filter = ("category_id",)
    search_fields = ("audit_id", "title")
    readonly_fields = ("audit_id",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
