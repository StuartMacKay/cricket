from django.urls import path

from metrics.views.page import PageDetailView, PageListView
from metrics.views.snapshot import SnapshotView

urlpatterns = [
    path("snapshot/<int:pk>/", SnapshotView.as_view()),
    path("snapshot/<int:pk>/page/", PageListView.as_view(), name="snapshot-pages"),
    path("page/<int:pk>/", PageDetailView.as_view()),
]
