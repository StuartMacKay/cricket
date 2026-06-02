"""Tests for the Lighthouse jobs endpoint."""

import pytest

from tests.factories import LighthouseJobFactory, SiteFactory

pytestmark = pytest.mark.django_db


class TestListLighthouseJobs:
    def test_requires_auth(self, client):
        site = SiteFactory()
        assert client.get(f"/api/sites/{site.slug}/lighthouse/jobs/").status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        LighthouseJobFactory(site=site)
        assert auth_client.get(f"/api/sites/{site.slug}/lighthouse/jobs/").status_code == 200

    def test_lists_site_jobs(self, auth_client):
        site = SiteFactory()
        LighthouseJobFactory(site=site)
        LighthouseJobFactory(site=site)
        LighthouseJobFactory()  # different site
        data = auth_client.get(f"/api/sites/{site.slug}/lighthouse/jobs/").json()
        assert len(data) == 2

    def test_job_fields_present(self, auth_client):
        site = SiteFactory()
        LighthouseJobFactory(site=site, platform="desktop")
        job = auth_client.get(f"/api/sites/{site.slug}/lighthouse/jobs/").json()[0]
        assert job["platform"] == "desktop"
        assert "cat_performance" in job
        assert "cat_seo" in job
