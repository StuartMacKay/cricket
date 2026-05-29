"""Tests for the pages endpoints."""

import pytest

from tests.factories import (
    AuditDefinitionFactory,
    LHSnapshotFactory,
    PageAuditFactory,
    PageCategoryFactory,
    PageFactory,
    SiteFactory,
)

pytestmark = pytest.mark.django_db


def make_snapshot(site):
    """Return (sites_snapshot, lh_snapshot) pair for a given site."""
    lh = LHSnapshotFactory(snapshot__site=site)
    return lh.snapshot, lh


class TestListPages:
    def test_requires_auth(self, client):
        site = SiteFactory()
        sites_snapshot, _ = make_snapshot(site)
        response = client.get(f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        sites_snapshot, _ = make_snapshot(site)
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/")
        assert response.status_code == 200

    def test_lists_audited_pages(self, auth_client):
        site = SiteFactory()
        sites_snapshot, lh = make_snapshot(site)
        PageFactory(snapshot=lh, audited=True)
        PageFactory(snapshot=lh, audited=True)
        PageFactory(snapshot=lh, audited=False)  # should be excluded
        response = auth_client.get(f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/")
        data = response.json()
        # only audited pages returned
        assert data["count"] == 2

    def test_filter_by_rating_and_category(self, auth_client):
        site = SiteFactory()
        sites_snapshot, lh = make_snapshot(site)
        good_page = PageFactory(snapshot=lh, audited=True)
        PageCategoryFactory(page=good_page, category_id="accessibility", rating="good")
        poor_page = PageFactory(snapshot=lh, audited=True)
        PageCategoryFactory(page=poor_page, category_id="accessibility", rating="poor")

        response = auth_client.get(
            f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/",
            {"category": "accessibility", "rating": "poor"},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_invalid_rating_returns_422(self, auth_client):
        site = SiteFactory()
        sites_snapshot, _ = make_snapshot(site)
        response = auth_client.get(
            f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/",
            {"rating": "excellent"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_rating"
        assert "valid_values" in response.json()["error"]


class TestGetPage:
    def test_returns_200(self, auth_client):
        site = SiteFactory()
        sites_snapshot, lh = make_snapshot(site)
        page = PageFactory(snapshot=lh, audited=True)
        response = auth_client.get(
            f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/{page.pk}/"
        )
        assert response.status_code == 200

    def test_returns_404_for_missing_page(self, auth_client):
        site = SiteFactory()
        sites_snapshot, _ = make_snapshot(site)
        response = auth_client.get(
            f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/999999/"
        )
        assert response.status_code == 404

    def test_response_includes_audits(self, auth_client):
        site = SiteFactory()
        sites_snapshot, lh = make_snapshot(site)
        page = PageFactory(snapshot=lh, audited=True)
        audit_def = AuditDefinitionFactory(audit_id="color-contrast", category_id="accessibility")
        PageAuditFactory(page=page, audit=audit_def, score=100, rating="good")

        response = auth_client.get(
            f"/api/sites/{site.slug}/snapshots/{sites_snapshot.pk}/pages/{page.pk}/"
        )
        data = response.json()
        assert "audits" in data
        assert "color-contrast" in data["audits"]
        audit = data["audits"]["color-contrast"]
        assert audit["score"] == 100
        assert audit["rating"] == "good"
