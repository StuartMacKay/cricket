from django.views import generic


class RobotsView(generic.TemplateView):
    template_name = "robots.txt"
    content_type = "text/plain"
