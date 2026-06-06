from django.contrib import admin
from django.contrib.admin import register

from ..models import Definition


@register(Definition)
class DefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "audit")
    list_filter = ("audit",)
    ordering = ("name",)
    readonly_fields = ("created", "modified")
