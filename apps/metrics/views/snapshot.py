from django.template.defaultfilters import date
from django.views import generic

from metrics.models import Snapshot


class SnapshotView(generic.DetailView):
    template_name = "metrics/snapshot/index.html"
    queryset = Snapshot.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = self.object.data["categories"]
        context.update(
            {
                "categories": [
                    categories["performance"],
                    categories["accessibility"],
                    categories["best-practices"],
                    categories["seo"],
                ],
                "date": date(self.object.created, "jS F Y"),
                "pages": self.object.get_number_of_pages(),
                "platform": self.object.data["config"]["formFactor"],
                "time": date(self.object.created, "g:i a"),
                "url": self.object.site.url,
            }
        )

        for category in context["categories"]:
            key = f"{category['id']}_score_graph".replace("-", "_")
            context[key] = self.object.get_category_quantile_graph(category["id"])

        for category in ("accessibility", "best-practices", "seo"):
            key = f"{category}_audits_checklist".replace("-", "_")
            context[key] = self.object.category_checklist(category)

        return context
