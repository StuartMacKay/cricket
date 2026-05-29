from django.shortcuts import get_object_or_404
from django.views import generic

from sites.models import Site, Snapshot


class SiteListView(generic.ListView):
    template_name = "lighthouse/site/list.html"
    queryset = Site.objects.order_by("name")
    context_object_name = "sites"


class SiteSnapshotListView(generic.ListView):
    template_name = "lighthouse/site/snapshots.html"
    context_object_name = "snapshots"
    paginate_by = 20

    def get_site(self):
        if not hasattr(self, "_site"):
            self._site = get_object_or_404(Site, pk=self.kwargs["pk"])
        return self._site

    def get_queryset(self):
        return Snapshot.objects.filter(site=self.get_site()).order_by("-created")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site"] = self.get_site()
        return context
