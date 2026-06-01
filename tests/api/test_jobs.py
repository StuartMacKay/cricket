"""Tests for the jobs endpoints."""

import pytest

from tests.factories import ScanFactory, SiteFactory

pytestmark = pytest.mark.django_db


class TestListJobs:
    def test_requires_auth(self, client):
        response = client.get("/api/jobs/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        response = auth_client.get("/api/jobs/")
        assert response.status_code == 200

    def test_lists_recent_scans(self, auth_client):
        ScanFactory(status="running")
        ScanFactory(status="complete")
        response = auth_client.get("/api/jobs/")
        assert len(response.json()) == 2


class TestGetJob:
    def test_returns_200_for_running_scan(self, auth_client):
        scan = ScanFactory(status="running")
        response = auth_client.get(f"/api/jobs/{scan.pk}/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["retry_after"] == 30

    def test_returns_result_url_when_complete(self, auth_client):
        site = SiteFactory()
        scan = ScanFactory(site=site, status="complete")
        response = auth_client.get(f"/api/jobs/{scan.pk}/")
        data = response.json()
        assert data["result_url"] is not None
        assert str(scan.pk) in data["result_url"]

    def test_returns_404_for_missing_job(self, auth_client):
        response = auth_client.get("/api/jobs/999999/")
        assert response.status_code == 404
