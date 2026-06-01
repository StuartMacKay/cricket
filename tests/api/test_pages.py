"""Tests for the pages endpoints."""

import pytest

from tests.factories import (
    AuditDefinitionFactory,
    LighthouseRunFactory,
    PageAuditFactory,
    PageCategoryFactory,
    PageFactory,
    ScanFactory,
    SiteFactory,
)

pytestmark = pytest.mark.django_db


def make_scan(site):
    """Return (scan, lh_run) pair for a given site."""
    lh = LighthouseRunFactory(scan__site=site)
    return lh.scan, lh


class TestListPages:
    def test_requires_auth(self, client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        response = client.get(f"/api/sites/{site.slug}/scans/{scan.pk}/pages/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        response = auth_client.get(f"/api/sites/{site.slug}/scans/{scan.pk}/pages/")
        assert response.status_code == 200

    def test_lists_all_pages(self, auth_client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        PageFactory(scan=scan)
        PageFactory(scan=scan)
        response = auth_client.get(f"/api/sites/{site.slug}/scans/{scan.pk}/pages/")
        data = response.json()
        assert data["count"] == 2

    def test_filter_by_rating_and_category(self, auth_client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        good_page = PageFactory(scan=scan)
        PageCategoryFactory(page=good_page, category_id="accessibility", rating="good")
        poor_page = PageFactory(scan=scan)
        PageCategoryFactory(page=poor_page, category_id="accessibility", rating="poor")

        response = auth_client.get(
            f"/api/sites/{site.slug}/scans/{scan.pk}/pages/",
            {"category": "accessibility", "rating": "poor"},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_invalid_rating_returns_422(self, auth_client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        response = auth_client.get(
            f"/api/sites/{site.slug}/scans/{scan.pk}/pages/",
            {"rating": "excellent"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_rating"
        assert "valid_values" in response.json()["error"]


class TestGetPage:
    def test_returns_200(self, auth_client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        page = PageFactory(scan=scan)
        response = auth_client.get(
            f"/api/sites/{site.slug}/scans/{scan.pk}/pages/{page.pk}/"
        )
        assert response.status_code == 200

    def test_returns_404_for_missing_page(self, auth_client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        response = auth_client.get(
            f"/api/sites/{site.slug}/scans/{scan.pk}/pages/999999/"
        )
        assert response.status_code == 404

    def test_response_includes_audits(self, auth_client):
        site = SiteFactory()
        scan, _ = make_scan(site)
        page = PageFactory(scan=scan)
        audit_def = AuditDefinitionFactory(audit_id="color-contrast", category_id="accessibility")
        PageAuditFactory(page=page, audit=audit_def, score=100, rating="good")

        response = auth_client.get(
            f"/api/sites/{site.slug}/scans/{scan.pk}/pages/{page.pk}/"
        )
        data = response.json()
        assert "audits" in data
        assert "color-contrast" in data["audits"]
        audit = data["audits"]["color-contrast"]
        assert audit["score"] == 100
        assert audit["rating"] == "good"
