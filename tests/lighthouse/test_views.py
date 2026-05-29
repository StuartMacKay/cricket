"""
Unit tests for the lighthouse views.

Covers:
  SnapshotView   – detail page for a completed snapshot
  PageListView   – paginated page list with optional rating/category filters
  PageDetailView – detail page for a single audited page
"""

import pytest
from django.urls import reverse

from lighthouse.models import SnapshotCategory
from tests.factories import (
    LHSnapshotFactory,
    PageCategoryFactory,
    PageFactory,
    SnapshotCategoryFactory,
)

pytestmark = pytest.mark.django_db

SNAPSHOT_URL = "/audits/snapshot/{pk}/"
PAGE_URL = "/audits/page/{pk}/"


# ---------------------------------------------------------------------------
# SnapshotView
# ---------------------------------------------------------------------------


class TestSnapshotView:
    def test_returns_200_for_existing_snapshot(self, client):
        snapshot = LHSnapshotFactory(status="complete", page_count=1)
        SnapshotCategoryFactory(snapshot=snapshot, category_id="performance", title="Performance")
        SnapshotCategoryFactory(snapshot=snapshot, category_id="accessibility", title="Accessibility")
        SnapshotCategoryFactory(snapshot=snapshot, category_id="best-practices", title="Best Practices")
        SnapshotCategoryFactory(snapshot=snapshot, category_id="seo", title="SEO")
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert response.status_code == 200

    def test_returns_404_for_missing_snapshot(self, client):
        response = client.get(SNAPSHOT_URL.format(pk=999999))
        assert response.status_code == 404

    def test_context_contains_category_results(self, client):
        snapshot = LHSnapshotFactory(status="complete", page_count=1)
        SnapshotCategoryFactory(snapshot=snapshot, category_id="performance")
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert "category_results" in response.context

    def test_context_contains_page_count(self, client):
        snapshot = LHSnapshotFactory(status="complete", page_count=3)
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert response.context["pages"] == 3

    def test_context_contains_platform(self, client):
        snapshot = LHSnapshotFactory(snapshot__platform="desktop", page_count=1)
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert response.context["platform"] == "desktop"


# ---------------------------------------------------------------------------
# PageListView
# ---------------------------------------------------------------------------


class TestPageListView:
    def test_returns_200_for_existing_snapshot(self, client):
        snapshot = LHSnapshotFactory()
        PageFactory(snapshot=snapshot, audited=True)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        response = client.get(url)
        assert response.status_code == 200

    def test_returns_404_for_missing_snapshot(self, client):
        url = reverse("snapshot-pages", kwargs={"pk": 999999})
        response = client.get(url)
        assert response.status_code == 404

    def test_lists_pages_for_snapshot(self, client):
        snapshot = LHSnapshotFactory()
        PageFactory(snapshot=snapshot, audited=True)
        PageFactory(snapshot=LHSnapshotFactory(), audited=True)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        response = client.get(url)
        assert response.context["object_list"].count() == 1

    def test_filter_by_category_and_rating(self, client):
        snapshot = LHSnapshotFactory()
        page = PageFactory(snapshot=snapshot, audited=True)
        PageCategoryFactory(page=page, category_id="accessibility", rating="good", score=90)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        response = client.get(url, {"category": "accessibility", "rating": "good"})
        assert response.status_code == 200
        assert response.context["object_list"].count() == 1

    def test_filter_with_no_matching_pages(self, client):
        snapshot = LHSnapshotFactory()
        page = PageFactory(snapshot=snapshot, audited=True)
        PageCategoryFactory(page=page, category_id="accessibility", rating="good", score=90)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        response = client.get(url, {"category": "accessibility", "rating": "poor"})
        assert response.context["object_list"].count() == 0


# ---------------------------------------------------------------------------
# PageDetailView
# ---------------------------------------------------------------------------


class TestPageDetailView:
    def test_returns_200_for_existing_page(self, client):
        page = PageFactory(audited=True)
        response = client.get(PAGE_URL.format(pk=page.pk))
        assert response.status_code == 200

    def test_returns_404_for_missing_page(self, client):
        response = client.get(PAGE_URL.format(pk=999999))
        assert response.status_code == 404

    def test_context_contains_category_order(self, client):
        page = PageFactory(audited=True)
        response = client.get(PAGE_URL.format(pk=page.pk))
        assert response.context["category_order"] == [
            "performance",
            "accessibility",
            "best-practices",
            "seo",
        ]

    def test_context_contains_ordered_categories(self, client):
        page = PageFactory(audited=True)
        PageCategoryFactory(page=page, category_id="performance", title="Performance")
        PageCategoryFactory(page=page, category_id="accessibility", title="Accessibility")
        response = client.get(PAGE_URL.format(pk=page.pk))
        assert "ordered_categories" in response.context
