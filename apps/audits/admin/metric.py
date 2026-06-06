from django.contrib import admin
from django.contrib.admin import register

from ..models import Metric


@register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ("definition", "score", "rating", "value", "units", "created")
    readonly_fields = ("created",)
