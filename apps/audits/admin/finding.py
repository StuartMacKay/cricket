from django.contrib import admin
from django.contrib.admin import register

from ..models import Finding


@register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = ("type", "title", "severity", "page", "source", "created")
    list_filter = ("type", "severity")
    ordering = ("-created",)
    readonly_fields = ("created",)
