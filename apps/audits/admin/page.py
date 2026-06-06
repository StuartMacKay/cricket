from django.contrib import admin
from django.contrib.admin import register

from ..models import Page


@register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("url", "site")
    search_fields = ("url",)
    readonly_fields = ("created", "modified")
