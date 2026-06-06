"""Tests for the api sites endpoints."""

import pytest

from tests.factories import SiteFactory

pytestmark = pytest.mark.django_db


class TestListSites:
    def test_requires_auth(self, client):
        assert client.get("/api/sites/").status_code == 401

    def test_returns_200(self, auth_client):
        assert auth_client.get("/api/sites/").status_code == 200

    def test_lists_all_sites(self, auth_client):
        SiteFactory()
        SiteFactory()
        data = auth_client.get("/api/sites/").json()
        assert len(data) == 2

    def test_site_fields_present(self, auth_client):
        SiteFactory()
        site = auth_client.get("/api/sites/").json()[0]
        assert "slug" in site
        assert "name" in site
        assert "url" in site
        assert "environment" in site


class TestGetSite:
    def test_returns_200_for_existing(self, auth_client):
        site = SiteFactory()
        assert auth_client.get(f"/api/sites/{site.slug}/").status_code == 200

    def test_returns_404_for_missing(self, auth_client):
        assert auth_client.get("/api/sites/no-such-site/").status_code == 404
