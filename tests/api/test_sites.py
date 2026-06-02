"""Tests for the sites endpoints."""

import pytest

from api.models import APIKey
from tests.factories import SiteFactory

pytestmark = pytest.mark.django_db


class TestListSites:
    def test_requires_auth(self, client):
        assert client.get("/api/sites/").status_code == 401

    def test_returns_200(self, auth_client):
        assert auth_client.get("/api/sites/").status_code == 200

    def test_lists_all_sites(self, auth_client):
        SiteFactory(); SiteFactory()
        assert len(auth_client.get("/api/sites/").json()) == 2

    def test_site_fields_present(self, auth_client):
        SiteFactory(name="Test Site")
        site = auth_client.get("/api/sites/").json()[0]
        assert "slug" in site
        assert "name" in site
        assert "primary_url" in site

    def test_scoped_key_sees_only_its_site(self, client):
        site_a = SiteFactory()
        SiteFactory()
        key = APIKey.objects.create(name="scoped", site=site_a)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {key.key}"
        data = client.get("/api/sites/").json()
        assert len(data) == 1
        assert data[0]["slug"] == site_a.slug


class TestGetSite:
    def test_returns_200(self, auth_client):
        site = SiteFactory()
        assert auth_client.get(f"/api/sites/{site.slug}/").status_code == 200

    def test_returns_404_for_missing(self, auth_client):
        assert auth_client.get("/api/sites/no-such-site/").status_code == 404

    def test_scoped_key_cannot_access_other_site(self, client):
        site_a = SiteFactory()
        site_b = SiteFactory()
        key = APIKey.objects.create(name="scoped", site=site_a)
        client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {key.key}"
        assert client.get(f"/api/sites/{site_b.slug}/").status_code == 403
