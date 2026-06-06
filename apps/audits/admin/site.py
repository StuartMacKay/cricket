from django.contrib import admin
from django.contrib.admin import register

from ..models import Site


@register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "environment", "url")
    list_filter = ("environment",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created", "modified")
