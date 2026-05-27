from django.views import generic

from metrics.models import Page, Rating, Snapshot


class PageListView(generic.ListView):
    template_name = "metrics/page/list.html"
    model = Page
    paginate_by = 50

    def get_filters(self):
        filters = {"snapshot_id": self.kwargs.get("pk")}

        rating = self.request.GET.get("rating")
        category = self.request.GET.get("category")
        audit = self.request.GET.get("audit")

        if category and rating:
            filters[
                "data__categories__{}__rating".format(category)
            ] = Rating.SLUGS.index(rating)
        elif audit and rating:
            filters["data__audits__{}__score".format(audit)] = Rating.SLUGS.index(
                rating
            )

        return filters

    def get_queryset(self):
        return self.model.objects.filter(**self.get_filters())


class PageDetailView(generic.DetailView):
    template_name = "metrics/page/detail.html"
    queryset = Page.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.object.data)
        context["category_order"] = [
            "performance",
            "accessibility",
            "best-practices",
            "seo",
        ]
        return context
