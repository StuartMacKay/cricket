"""Tests for the per-tool runs endpoints (Lighthouse as primary example)."""

import pytest

from tests.factories import (
    LighthouseJobFactory, LighthousePageFactory, LighthouseRunFactory,
    PageCategoryFactory, SiteFactory,
)

pytestmark = pytest.mark.django_db


class TestListLighthouseRuns:
    def test_requires_auth(self, client):
        site = SiteFactory()
        response = client.get(f"/api/sites/{site.slug}/lighthouse/runs/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site)
        response = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/")
        assert response.status_code == 200

    def test_returns_404_for_missing_site(self, auth_client):
        response = auth_client.get("/api/sites/no-site/lighthouse/runs/")
        assert response.status_code == 404

    def test_lists_only_site_runs(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site)
        LighthouseRunFactory(job__site=site)
        LighthouseRunFactory()  # different site
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/").json()
        assert data["count"] == 2

    def test_filter_by_status(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site, status="complete")
        LighthouseRunFactory(job__site=site, status="running")
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/", {"status": "complete"}).json()
        assert data["count"] == 1

    def test_filter_by_environment(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site, job__environment="staging")
        LighthouseRunFactory(job__site=site, job__environment="production")
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/", {"environment": "staging"}).json()
        assert data["count"] == 1

    def test_filter_by_category(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site, job__cat_performance=True, job__cat_seo=False)
        LighthouseRunFactory(job__site=site, job__cat_performance=False, job__cat_seo=True)
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/", {"cat_performance": "true"}).json()
        assert data["count"] == 1


class TestLatestLighthouseRun:
    def test_returns_404_when_no_complete_run(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site, status="pending")
        response = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/latest/")
        assert response.status_code == 404

    def test_returns_most_recent_complete(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site, status="complete")
        r2 = LighthouseRunFactory(job__site=site, status="complete")
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/latest/").json()
        assert data["id"] == r2.pk

    def test_response_includes_categories(self, auth_client):
        site = SiteFactory()
        run  = LighthouseRunFactory(job__site=site, status="complete")
        page = LighthousePageFactory(run=run)
        PageCategoryFactory(page=page, category_id="performance")
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/latest/").json()
        assert "categories" in data
        assert "performance" in data["categories"]

    def test_response_includes_environment(self, auth_client):
        site = SiteFactory()
        LighthouseRunFactory(job__site=site, status="complete", job__environment="staging")
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/runs/latest/").json()
        assert data["environment"] == "staging"
