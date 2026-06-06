from django.contrib import admin
from django.contrib.admin import register

from ..models import Audit


@register(Audit)
class AuditAdmin(admin.ModelAdmin):
    list_display = ("name", "task")
    ordering = ("name",)
    readonly_fields = ("created", "modified")
