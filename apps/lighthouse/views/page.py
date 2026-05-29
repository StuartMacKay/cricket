from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views import generic

from lighthouse.models import Page, Snapshot


class PageListView(generic.ListView):
    template_name = "lighthouse/page/list.html"
    model = Page
    paginate_by = 50

    def get_snapshot(self):
        if not hasattr(self, "_snapshot"):
            self._snapshot = get_object_or_404(Snapshot, pk=self.kwargs["pk"])
        return self._snapshot

    def get_filters(self):
        filters = {"snapshot": self.get_snapshot()}

        rating = self.request.GET.get("rating")
        category = self.request.GET.get("category")

        if category and rating:
            filters["categories__category_id"] = category
            filters["categories__rating"] = rating

        return filters

    def get_queryset(self):
        return self.model.objects.filter(**self.get_filters()).distinct().order_by("url")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["snapshot"] = self.get_snapshot()
        return context


class PageDetailView(generic.DetailView):
    template_name = "lighthouse/page/detail.html"
    queryset = Page.objects.prefetch_related(
        "categories", "audits__audit"
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.object

        CATEGORY_ORDER = [
            "performance",
            "accessibility",
            "best-practices",
            "seo",
        ]

        categories = {c.category_id: c for c in page.categories.all()}
        ordered_categories = [
            categories[cid] for cid in CATEGORY_ORDER if cid in categories
        ]

        audits_by_category: dict[str, list] = {}
        for audit in page.audits.select_related("audit").all():
            cat_id = audit.audit.category_id
            audits_by_category.setdefault(cat_id, []).append(audit)

        context.update(
            {
                "category_order": CATEGORY_ORDER,
                "ordered_categories": ordered_categories,
                "audits_by_category": audits_by_category,
            }
        )
        return context


class PageReportView(generic.DetailView):
    """Serve the self-contained Lighthouse HTML report for a single page."""

    queryset = Page.objects.all()

    def get(self, request, *args, **kwargs):
        page = self.get_object()
        if not page.html_report:
            raise Http404("No HTML report is available for this page.")
        with page.html_report.open() as fp:
            content = fp.read()
        return HttpResponse(content, content_type="text/html; charset=utf-8")
