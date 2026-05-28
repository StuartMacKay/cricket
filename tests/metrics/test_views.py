"""
Unit tests for the metrics views.

Covers:
  SnapshotView   – detail page for a completed snapshot
  PageListView   – paginated page list with optional rating/category filters
  PageDetailView – detail page for a single audited page
"""

import pytest
from django.urls import reverse

from tests.factories import PageFactory, SiteFactory, SnapshotFactory

pytestmark = pytest.mark.django_db

SNAPSHOT_URL = "/audits/snapshot/{pk}/"
PAGE_URL = "/audits/page/{pk}/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def snapshot_with_data(page_data):
    """Return a Snapshot that has aggregated metrics (simulating a completed run)."""
    snapshot = SnapshotFactory(
        data={
            "config": {"formFactor": "mobile"},
            "categories": {
                "performance": {
                    "id": "performance",
                    "title": "Performance",
                    "type": "numeric",
                    "score": 85,
                    "rating": 1,
                    "quantile": 17,
                    "audits": ["first-contentful-paint"],
                    "ratings": [0, 1, 0],
                    "quantiles": [0] * 17 + [1, 0, 0],
                    "urls": [],
                },
                "accessibility": {
                    "id": "accessibility",
                    "title": "Accessibility",
                    "type": "numeric",
                    "score": 90,
                    "rating": 2,
                    "quantile": 18,
                    "audits": ["color-contrast"],
                    "ratings": [0, 0, 1],
                    "quantiles": [0] * 18 + [1, 0],
                    "urls": [],
                },
                "best-practices": {
                    "id": "best-practices",
                    "title": "Best Practices",
                    "type": "numeric",
                    "score": 95,
                    "rating": 2,
                    "quantile": 19,
                    "audits": ["is-on-https"],
                    "ratings": [0, 0, 1],
                    "quantiles": [0] * 19 + [1],
                    "urls": [],
                },
                "seo": {
                    "id": "seo",
                    "title": "SEO",
                    "type": "numeric",
                    "score": 88,
                    "rating": 1,
                    "quantile": 17,
                    "audits": ["meta-description"],
                    "ratings": [0, 1, 0],
                    "quantiles": [0] * 17 + [1, 0, 0],
                    "urls": [],
                },
            },
            "audits": {
                "first-contentful-paint": {
                    "id": "first-contentful-paint",
                    "title": "First Contentful Paint",
                    "category": "performance",
                    "weight": 10,
                    "type": "numeric",
                    "score": 90,
                    "value": 1200,
                    "units": "millisecond",
                    "quantile": 18,
                    "rating": 2,
                    "ratings": [0, 0, 1],
                    "quantiles": [0] * 18 + [1, 0],
                    "urls": [],
                },
                "color-contrast": {
                    "id": "color-contrast",
                    "title": "Background and foreground colors have sufficient contrast",
                    "category": "accessibility",
                    "weight": 3,
                    "type": "binary",
                    "score": 1,
                    "rating": 2,
                    "scores": [0, 1],
                },
                "is-on-https": {
                    "id": "is-on-https",
                    "title": "Uses HTTPS",
                    "category": "best-practices",
                    "weight": 0,
                    "type": "binary",
                    "score": 1,
                    "rating": 2,
                    "scores": [0, 1],
                },
                "meta-description": {
                    "id": "meta-description",
                    "title": "Document has a meta description",
                    "category": "seo",
                    "weight": 0,
                    "type": "binary",
                    "score": 0,
                    "rating": 0,
                    "scores": [1, 0],
                },
            },
        }
    )
    PageFactory(snapshot=snapshot, audited=True, data=page_data)
    return snapshot


# ---------------------------------------------------------------------------
# SnapshotView
# ---------------------------------------------------------------------------


class TestSnapshotView:
    def test_returns_200_for_existing_snapshot(self, client, page_data):
        snapshot = snapshot_with_data(page_data)
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert response.status_code == 200

    def test_returns_404_for_missing_snapshot(self, client):
        response = client.get(SNAPSHOT_URL.format(pk=999999))
        assert response.status_code == 404

    def test_context_contains_categories(self, client, page_data):
        snapshot = snapshot_with_data(page_data)
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert "categories" in response.context
        ids = [c["id"] for c in response.context["categories"]]
        assert ids == ["performance", "accessibility", "best-practices", "seo"]

    def test_context_contains_page_count(self, client, page_data):
        snapshot = snapshot_with_data(page_data)
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert response.context["pages"] == 1

    def test_context_contains_platform(self, client, page_data):
        snapshot = snapshot_with_data(page_data)
        response = client.get(SNAPSHOT_URL.format(pk=snapshot.pk))
        assert response.context["platform"] == "mobile"


# ---------------------------------------------------------------------------
# PageListView
# ---------------------------------------------------------------------------


class TestPageListView:
    def test_returns_200_for_existing_snapshot(self, client, page_data):
        snapshot = SnapshotFactory()
        PageFactory(snapshot=snapshot, audited=True, data=page_data)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        response = client.get(url)
        assert response.status_code == 200

    def test_lists_pages_for_snapshot(self, client, page_data):
        snapshot = SnapshotFactory()
        PageFactory(snapshot=snapshot, audited=True, data=page_data)
        # Page belonging to a different snapshot — should not appear
        PageFactory(snapshot=SnapshotFactory(), audited=True, data=page_data)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        response = client.get(url)
        assert response.context["object_list"].count() == 1

    def test_filter_by_category_and_rating(self, client, page_data):
        snapshot = SnapshotFactory()
        PageFactory(snapshot=snapshot, audited=True, data=page_data)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        # accessibility score=90 → rating index 2 = 'good'
        response = client.get(url, {"category": "accessibility", "rating": "good"})
        assert response.status_code == 200
        assert response.context["object_list"].count() == 1

    def test_filter_with_no_matching_pages(self, client, page_data):
        snapshot = SnapshotFactory()
        PageFactory(snapshot=snapshot, audited=True, data=page_data)
        url = reverse("snapshot-pages", kwargs={"pk": snapshot.pk})
        # accessibility is GOOD (2), filter for POOR (0) → no results
        response = client.get(url, {"category": "accessibility", "rating": "poor"})
        assert response.context["object_list"].count() == 0


# ---------------------------------------------------------------------------
# PageDetailView
# ---------------------------------------------------------------------------


class TestPageDetailView:
    def test_returns_200_for_existing_page(self, client, page_data):
        page = PageFactory(audited=True, data=page_data)
        response = client.get(PAGE_URL.format(pk=page.pk))
        assert response.status_code == 200

    def test_returns_404_for_missing_page(self, client):
        response = client.get(PAGE_URL.format(pk=999999))
        assert response.status_code == 404

    def test_context_contains_category_order(self, client, page_data):
        page = PageFactory(audited=True, data=page_data)
        response = client.get(PAGE_URL.format(pk=page.pk))
        assert response.context["category_order"] == [
            "performance",
            "accessibility",
            "best-practices",
            "seo",
        ]

    def test_context_contains_page_data(self, client, page_data):
        page = PageFactory(audited=True, data=page_data)
        response = client.get(PAGE_URL.format(pk=page.pk))
        assert "categories" in response.context
        assert "audits" in response.context
