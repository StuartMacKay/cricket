"""Tests for the snapshots endpoints."""

from unittest.mock import patch

import pytest

from tests.factories import LHSnapshotFactory, SiteFactory, SnapshotCategoryFactory, SnapshotFactory

pytestmark = pytest.mark.django_db

PATCH_TARGETS = [
    "lighthouse.tasks.take_lighthouse_snapshot",
    "headers.tasks.take_header_snapshot",
    "pageweight.tasks.take_weight_snapshot",
]


def patch_all_tasks():
    """Context manager that suppresses all three audit tasks."""
    from contextlib import ExitStack
    stack = ExitStack()
    mocks = [stack.enter_context(patch(t)) for t in PATCH_TARGETS]
    return stack, mocks


class TestListSnapshots:
    def test_requires_auth(self, client):
        site = SiteFactory()
        response = client.get(f"/api/sites/{site.slug}/snapshots/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        SnapshotFactory(site=site)
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/")
        assert response.status_code == 200

    def test_returns_404_for_missing_site(self, auth_client):
        response = auth_client.get("/api/sites/no-site/snapshots/")
        assert response.status_code == 404

    def test_lists_only_site_snapshots(self, auth_client):
        site = SiteFactory()
        SnapshotFactory(site=site)
        SnapshotFactory(site=site)
        SnapshotFactory()  # different site
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/")
        data = response.json()
        assert data["count"] == 2

    def test_response_has_pagination_fields(self, auth_client):
        site = SiteFactory()
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/")
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "truncated" in data


class TestLatestSnapshot:
    def test_returns_404_when_no_complete_snapshot(self, auth_client):
        site = SiteFactory()
        SnapshotFactory(site=site, status="pending")
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/latest/")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "no_complete_snapshot"

    def test_returns_most_recent_complete(self, auth_client):
        site = SiteFactory()
        s1 = SnapshotFactory(site=site, status="complete")
        s2 = SnapshotFactory(site=site, status="complete")
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/latest/")
        assert response.status_code == 200
        assert response.json()["id"] == s2.pk

    def test_response_includes_categories(self, auth_client):
        site = SiteFactory()
        sites_snapshot = SnapshotFactory(site=site, status="complete")
        lh_snapshot = LHSnapshotFactory(snapshot=sites_snapshot)
        SnapshotCategoryFactory(snapshot=lh_snapshot, category_id="performance")
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/latest/")
        assert "categories" in response.json()
        assert "performance" in response.json()["categories"]


class TestCreateSnapshot:
    def test_returns_409_when_snapshot_in_flight(self, auth_client):
        site = SiteFactory()
        SnapshotFactory(site=site, status="running")
        with patch("lighthouse.tasks.take_lighthouse_snapshot"):
            response = auth_client.post(
                f"/api/sites/{site.slug}/snapshots/",
                content_type="application/json",
                data={"force": False},
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "snapshot_in_progress"

    def test_force_bypasses_conflict_check(self, auth_client):
        site = SiteFactory()
        SnapshotFactory(site=site, status="running")
        with patch("lighthouse.tasks.take_lighthouse_snapshot"):
            with patch("headers.tasks.take_header_snapshot"):
                with patch("pageweight.tasks.take_weight_snapshot"):
                    response = auth_client.post(
                        f"/api/sites/{site.slug}/snapshots/",
                        content_type="application/json",
                        data={"force": True},
                    )
        assert response.status_code == 202

    def test_returns_202_for_new_snapshot(self, auth_client):
        site = SiteFactory()
        with patch("lighthouse.tasks.take_lighthouse_snapshot"):
            with patch("headers.tasks.take_header_snapshot"):
                with patch("pageweight.tasks.take_weight_snapshot"):
                    response = auth_client.post(
                        f"/api/sites/{site.slug}/snapshots/",
                        content_type="application/json",
                        data={},
                    )
        assert response.status_code == 202

    def test_response_contains_poll_url(self, auth_client):
        site = SiteFactory()
        with patch("lighthouse.tasks.take_lighthouse_snapshot"):
            with patch("headers.tasks.take_header_snapshot"):
                with patch("pageweight.tasks.take_weight_snapshot"):
                    data = auth_client.post(
                        f"/api/sites/{site.slug}/snapshots/",
                        content_type="application/json",
                        data={},
                    ).json()
        assert "poll_url" in data
        assert data["poll_url"].startswith("/api/jobs/")
