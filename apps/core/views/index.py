from django.urls import reverse_lazy
from django.views.generic import RedirectView


class IndexView(RedirectView):
    url = reverse_lazy("admin:index")
