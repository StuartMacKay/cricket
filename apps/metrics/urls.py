from django.urls import path

from metrics.views.page import PageDetailView, PageListView, PageReportView
from metrics.views.site import SiteListView, SiteSnapshotListView
from metrics.views.snapshot import SnapshotView

urlpatterns = [
    path("", SiteListView.as_view(), name="site-list"),
    path("site/<int:pk>/", SiteSnapshotListView.as_view(), name="site-snapshots"),
    path("snapshot/<int:pk>/", SnapshotView.as_view(), name="snapshot-detail"),
    path("snapshot/<int:pk>/page/", PageListView.as_view(), name="snapshot-pages"),
    path("page/<int:pk>/", PageDetailView.as_view(), name="page-detail"),
    path("page/<int:pk>/report/", PageReportView.as_view(), name="page-report"),
]
