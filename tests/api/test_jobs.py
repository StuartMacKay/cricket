"""Tests for the jobs endpoints."""

import pytest

from tests.factories import SiteFactory, SnapshotFactory

pytestmark = pytest.mark.django_db


class TestListJobs:
    def test_requires_auth(self, client):
        response = client.get("/api/jobs/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        response = auth_client.get("/api/jobs/")
        assert response.status_code == 200

    def test_lists_recent_snapshots(self, auth_client):
        SnapshotFactory(status="running")
        SnapshotFactory(status="complete")
        response = auth_client.get("/api/jobs/")
        assert len(response.json()) == 2


class TestGetJob:
    def test_returns_200_for_running_snapshot(self, auth_client):
        snapshot = SnapshotFactory(status="running")
        response = auth_client.get(f"/api/jobs/{snapshot.pk}/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["retry_after"] == 30

    def test_returns_result_url_when_complete(self, auth_client):
        site = SiteFactory()
        snapshot = SnapshotFactory(site=site, status="complete")
        response = auth_client.get(f"/api/jobs/{snapshot.pk}/")
        data = response.json()
        assert data["result_url"] is not None
        assert str(snapshot.pk) in data["result_url"]

    def test_returns_404_for_missing_job(self, auth_client):
        response = auth_client.get("/api/jobs/999999/")
        assert response.status_code == 404
