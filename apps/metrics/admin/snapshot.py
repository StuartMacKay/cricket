from django.contrib import admin
from django.db import models

from django_json_widget.widgets import JSONEditorWidget

from ..models import Snapshot


@admin.register(Snapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ("site", "created")
    ordering = ("-created",)
    search_fields = ("site",)
    readonly_fields = (
        "site",
        "created",
        "modified",
    )

    formfield_overrides = {
        models.JSONField: {"widget": JSONEditorWidget},
    }

    def has_add_permission(self, request, obj=None):
        return False
