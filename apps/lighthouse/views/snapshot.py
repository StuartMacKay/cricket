from django.template.defaultfilters import date
from django.views import generic

from lighthouse.models import Snapshot


class SnapshotView(generic.DetailView):
    template_name = "lighthouse/snapshot/detail.html"
    queryset = Snapshot.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = self.object

        category_results = snapshot.category_results.order_by("category_id")

        context.update(
            {
                "date": date(snapshot.created, "jS F Y"),
                "time": date(snapshot.created, "g:i a"),
                "url": snapshot.site.url,
                "pages": snapshot.page_count or snapshot.get_number_of_pages(),
                "platform": snapshot.platform,
                "category_results": category_results,
            }
        )
        return context
