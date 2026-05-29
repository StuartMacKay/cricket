from django.contrib import admin

from ..models import AuditDefinition, SnapshotAudit, SnapshotCategory


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


@admin.register(SnapshotCategory)
class SnapshotCategoryAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "category_id", "poor_count", "needs_count", "good_count", "score_avg")
    list_filter = ("category_id",)
    readonly_fields = ("snapshot", "category_id", "title", "poor_count", "needs_count", "good_count", "score_avg")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SnapshotAudit)
class SnapshotAuditAdmin(admin.ModelAdmin):
    list_display = ("snapshot", "audit", "poor_count", "needs_count", "good_count")
    readonly_fields = ("snapshot", "audit", "poor_count", "needs_count", "good_count")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
