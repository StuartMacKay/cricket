"""Tests for the scans endpoints."""

from unittest.mock import patch

import pytest

from tests.factories import LighthouseRunFactory, PageCategoryFactory, PageFactory, ScanFactory, SiteFactory

pytestmark = pytest.mark.django_db

PATCH_TARGETS = [
    "sites.tasks.take_site_scan",
]


class TestListScans:
    def test_requires_auth(self, client):
        site = SiteFactory()
        response = client.get(f"/api/sites/{site.slug}/scans/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site)
        response = auth_client.get(f"/api/sites/{site.slug}/scans/")
        assert response.status_code == 200

    def test_returns_404_for_missing_site(self, auth_client):
        response = auth_client.get("/api/sites/no-site/scans/")
        assert response.status_code == 404

    def test_lists_only_site_scans(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site)
        ScanFactory(site=site)
        ScanFactory()  # different site
        response = auth_client.get(f"/api/sites/{site.slug}/scans/")
        data = response.json()
        assert data["count"] == 2

    def test_response_has_pagination_fields(self, auth_client):
        site = SiteFactory()
        response = auth_client.get(f"/api/sites/{site.slug}/scans/")
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "truncated" in data

    def test_filter_by_environment(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site, environment="staging")
        ScanFactory(site=site, environment="production")
        response = auth_client.get(f"/api/sites/{site.slug}/scans/", {"environment": "staging"})
        data = response.json()
        assert data["count"] == 1


class TestLatestScan:
    def test_returns_404_when_no_complete_scan(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site, status="pending")
        response = auth_client.get(f"/api/sites/{site.slug}/scans/latest/")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "no_complete_scan"

    def test_returns_most_recent_complete(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site, status="complete")
        s2 = ScanFactory(site=site, status="complete")
        response = auth_client.get(f"/api/sites/{site.slug}/scans/latest/")
        assert response.status_code == 200
        assert response.json()["id"] == s2.pk

    def test_response_includes_categories(self, auth_client):
        site = SiteFactory()
        scan = ScanFactory(site=site, status="complete")
        page = PageFactory(scan=scan)
        PageCategoryFactory(page=page, category_id="performance")
        response = auth_client.get(f"/api/sites/{site.slug}/scans/latest/")
        assert "categories" in response.json()
        assert "performance" in response.json()["categories"]

    def test_response_includes_environment(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site, status="complete", environment="staging")
        response = auth_client.get(f"/api/sites/{site.slug}/scans/latest/")
        assert response.json()["environment"] == "staging"


class TestCreateScan:
    def test_returns_409_when_scan_in_flight(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site, status="running")
        with patch("sites.tasks.take_site_scan"):
            response = auth_client.post(
                f"/api/sites/{site.slug}/scans/",
                content_type="application/json",
                data={"force": False},
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "scan_in_progress"

    def test_force_bypasses_conflict_check(self, auth_client):
        site = SiteFactory()
        ScanFactory(site=site, status="running")
        with patch("sites.tasks.take_site_scan"):
            response = auth_client.post(
                f"/api/sites/{site.slug}/scans/",
                content_type="application/json",
                data={"force": True},
            )
        assert response.status_code == 202

    def test_returns_202_for_new_scan(self, auth_client):
        site = SiteFactory()
        with patch("sites.tasks.take_site_scan"):
            response = auth_client.post(
                f"/api/sites/{site.slug}/scans/",
                content_type="application/json",
                data={},
            )
        assert response.status_code == 202

    def test_response_contains_poll_url(self, auth_client):
        site = SiteFactory()
        with patch("sites.tasks.take_site_scan"):
            data = auth_client.post(
                f"/api/sites/{site.slug}/scans/",
                content_type="application/json",
                data={},
            ).json()
        assert "poll_url" in data
        assert data["poll_url"].startswith("/api/jobs/")
