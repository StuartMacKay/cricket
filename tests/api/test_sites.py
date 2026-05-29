"""Tests for the sites endpoints."""

import pytest

from tests.factories import SiteFactory, SnapshotFactory

pytestmark = pytest.mark.django_db


class TestListSites:
    def test_requires_auth(self, client):
        response = client.get("/api/sites/")
        assert response.status_code == 401

    def test_returns_200_with_auth(self, auth_client):
        response = auth_client.get("/api/sites/")
        assert response.status_code == 200

    def test_lists_all_sites(self, auth_client):
        SiteFactory()
        SiteFactory()
        response = auth_client.get("/api/sites/")
        assert len(response.json()) == 2

    def test_empty_when_no_sites(self, auth_client):
        response = auth_client.get("/api/sites/")
        assert response.json() == []

    def test_site_fields_present(self, auth_client):
        SiteFactory(name="Test Site")
        data = auth_client.get("/api/sites/").json()
        assert len(data) == 1
        site = data[0]
        assert "slug" in site
        assert "name" in site
        assert "url" in site
        assert "enabled" in site


class TestGetSite:
    def test_requires_auth(self, client):
        site = SiteFactory()
        response = client.get(f"/api/sites/{site.slug}/")
        assert response.status_code == 401

    def test_returns_200_for_existing_site(self, auth_client):
        site = SiteFactory()
        response = auth_client.get(f"/api/sites/{site.slug}/")
        assert response.status_code == 200

    def test_returns_404_for_missing_site(self, auth_client):
        response = auth_client.get("/api/sites/no-such-site/")
        assert response.status_code == 404

    def test_error_code_is_not_found(self, auth_client):
        response = auth_client.get("/api/sites/no-such-site/")
        assert response.json()["error"]["code"] == "not_found"

    def test_site_name_in_response(self, auth_client):
        site = SiteFactory(name="My Site")
        data = auth_client.get(f"/api/sites/{site.slug}/").json()
        assert data["name"] == "My Site"
