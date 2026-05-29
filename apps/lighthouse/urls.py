from django.urls import path

from lighthouse.views.page import PageDetailView, PageListView, PageReportView
from lighthouse.views.site import SiteListView, SiteSnapshotListView
from lighthouse.views.snapshot import SnapshotView

urlpatterns = [
    path("", SiteListView.as_view(), name="site-list"),
    path("site/<int:pk>/", SiteSnapshotListView.as_view(), name="site-snapshots"),
    path("snapshot/<int:pk>/", SnapshotView.as_view(), name="snapshot-detail"),
    path("snapshot/<int:pk>/page/", PageListView.as_view(), name="snapshot-pages"),
    path("page/<int:pk>/", PageDetailView.as_view(), name="page-detail"),
    path("page/<int:pk>/report/", PageReportView.as_view(), name="page-report"),
]
