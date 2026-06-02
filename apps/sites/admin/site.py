from django.contrib import admin
from django.contrib.admin import register

from ..models import Site


@register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display  = ("name", "slug", "primary_url")
    search_fields = ("name", "slug", "primary_url")
    ordering      = ("name",)
    readonly_fields = ("created", "modified")
