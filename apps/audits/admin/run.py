from django.contrib import admin
from django.contrib.admin import register

from ..models import Run


@register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display  = ("job", "status", "created")
    ordering = ("-created",)
    readonly_fields = ("created",)
