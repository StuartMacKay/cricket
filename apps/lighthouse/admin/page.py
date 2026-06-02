from django.contrib import admin
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

from ..models import Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display    = ("url", "run", "audited", "report_link", "created")
    list_filter     = ("audited",)
    ordering        = ("url",)
    search_fields   = ("url",)
    readonly_fields = ("run", "url", "report", "html_report", "report_link", "audited", "created", "modified")

    def has_add_permission(self, request, obj=None):    return False
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser

    @admin.display(description="Lighthouse report")
    def report_link(self, obj):
        if not obj.html_report:
            return "—"
        url = reverse("admin:lighthouse-page-report", kwargs={"pk": obj.pk})
        return format_html('<a href="{}" target="_blank">View report</a>', url)

    def get_urls(self):
        return [
            path(
                "<int:pk>/report/",
                self.admin_site.admin_view(self._serve_report),
                name="lighthouse-page-report",
            ),
        ] + super().get_urls()

    def _serve_report(self, request, pk):
        try:
            page = Page.objects.get(pk=pk)
        except Page.DoesNotExist:
            raise Http404
        if not page.html_report:
            raise Http404("No HTML report for this page.")
        with page.html_report.open() as fp:
            return HttpResponse(fp.read(), content_type="text/html; charset=utf-8")
