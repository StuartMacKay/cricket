from django.contrib import sitemaps
from django.urls import reverse


class SitemapView(sitemaps.Sitemap):
    priority = 1.0
    changefreq = "daily"

    def items(self):
        return ["index"]

    def location(self, item):
        return reverse(item)
