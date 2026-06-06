"""Tests for the api jobs endpoints."""

import pytest

from tests.factories import AuditFactory, JobFactory, SiteFactory

pytestmark = pytest.mark.django_db


class TestListJobs:
    def test_requires_auth(self, client):
        site = SiteFactory()
        assert client.get(f"/api/sites/{site.slug}/jobs/").status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        JobFactory(site=site, audits=[audit])
        assert auth_client.get(f"/api/sites/{site.slug}/jobs/").status_code == 200

    def test_job_fields(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        data = auth_client.get(f"/api/sites/{site.slug}/jobs/").json()
        assert len(data) == 1
        result = data[0]
        assert result["id"] == job.pk
        assert result["name"] == job.name
        assert result["enabled"] == job.enabled
        assert "audits" in result
        assert len(result["audits"]) == 1
        assert result["audits"][0]["slug"] == audit.slug

    def test_site_isolation(self, auth_client):
        site_a = SiteFactory()
        site_b = SiteFactory()
        JobFactory(site=site_a)
        JobFactory(site=site_b)
        data = auth_client.get(f"/api/sites/{site_a.slug}/jobs/").json()
        assert len(data) == 1

    def test_unknown_site_returns_404(self, auth_client):
        assert auth_client.get("/api/sites/nope/jobs/").status_code == 404


class TestGetJob:
    def test_returns_200_for_existing(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        assert auth_client.get(f"/api/sites/{site.slug}/jobs/{job.pk}/").status_code == 200

    def test_returns_404_for_wrong_site(self, auth_client):
        site_a = SiteFactory()
        site_b = SiteFactory()
        job = JobFactory(site=site_b)
        assert auth_client.get(f"/api/sites/{site_a.slug}/jobs/{job.pk}/").status_code == 404

    def test_returns_404_for_unknown_job(self, auth_client):
        site = SiteFactory()
        assert auth_client.get(f"/api/sites/{site.slug}/jobs/9999/").status_code == 404
