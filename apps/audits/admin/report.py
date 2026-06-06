from django.contrib import admin
from django.contrib.admin import register

from ..models import Report


@register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("page", "audit", "run", "created")
    readonly_fields = ("created", "modified")
