"""Tests for the Lighthouse pages endpoint."""

import pytest

from tests.factories import (
    AuditDefinitionFactory, LighthousePageFactory, LighthouseRunFactory,
    PageAuditFactory, PageCategoryFactory, SiteFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def site_and_run():
    site = SiteFactory()
    run  = LighthouseRunFactory(job__site=site, status="complete")
    return site, run


class TestListPages:
    def test_requires_auth(self, client, site_and_run):
        site, run = site_and_run
        assert client.get(f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/").status_code == 401

    def test_returns_200(self, auth_client, site_and_run):
        site, run = site_and_run
        assert auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/").status_code == 200

    def test_lists_pages(self, auth_client, site_and_run):
        site, run = site_and_run
        LighthousePageFactory(run=run)
        LighthousePageFactory(run=run)
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/").json()
        assert data["count"] == 2

    def test_filter_by_category_and_rating(self, auth_client, site_and_run):
        site, run = site_and_run
        good_page = LighthousePageFactory(run=run)
        PageCategoryFactory(page=good_page, category_id="accessibility", rating="good")
        poor_page = LighthousePageFactory(run=run)
        PageCategoryFactory(page=poor_page, category_id="accessibility", rating="poor")
        data = auth_client.get(
            f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/",
            {"category": "accessibility", "rating": "poor"},
        ).json()
        assert data["count"] == 1

    def test_invalid_rating_returns_422(self, auth_client, site_and_run):
        site, run = site_and_run
        response = auth_client.get(
            f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/",
            {"rating": "excellent"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_rating"


class TestGetPage:
    def test_returns_200(self, auth_client, site_and_run):
        site, run = site_and_run
        page = LighthousePageFactory(run=run)
        assert auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/{page.pk}/").status_code == 200

    def test_returns_404_for_missing(self, auth_client, site_and_run):
        site, run = site_and_run
        assert auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/999999/").status_code == 404

    def test_response_includes_audits(self, auth_client, site_and_run):
        site, run = site_and_run
        page = LighthousePageFactory(run=run)
        audit_def = AuditDefinitionFactory(audit_id="color-contrast", category_id="accessibility")
        PageAuditFactory(page=page, audit=audit_def, score=100, rating="good")
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/{run.pk}/pages/{page.pk}/").json()
        assert "audits" in data
        assert "color-contrast" in data["audits"]
        assert data["audits"]["color-contrast"]["score"] == 100
