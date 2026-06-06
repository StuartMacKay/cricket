"""Tests for the api definitions endpoints."""

import pytest

from tests.factories import AuditFactory, DefinitionFactory

pytestmark = pytest.mark.django_db


class TestListDefinitions:
    def test_requires_auth(self, client):
        assert client.get("/api/definitions/").status_code == 401

    def test_returns_200(self, auth_client):
        assert auth_client.get("/api/definitions/").status_code == 200

    def test_definitions_include_audit_info(self, auth_client):
        audit = AuditFactory()
        created = DefinitionFactory(audit=audit)
        data = auth_client.get("/api/definitions/").json()
        definition = next(d for d in data if d["slug"] == created.slug)
        assert "audit" in definition
        assert "slug" in definition["audit"]
        assert "name" in definition["audit"]

    def test_seeded_performance_definitions_present(self, auth_client):
        data = auth_client.get("/api/definitions/").json()
        slugs = {d["slug"] for d in data}
        for expected in [
            "first-contentful-paint",
            "largest-contentful-paint",
            "total-blocking-time",
            "cumulative-layout-shift",
            "speed-index",
        ]:
            assert expected in slugs


class TestGetDefinition:
    def test_returns_200_for_existing(self, auth_client):
        definition = DefinitionFactory()
        assert auth_client.get(f"/api/definitions/{definition.slug}/").status_code == 200

    def test_returns_404_for_missing(self, auth_client):
        assert auth_client.get("/api/definitions/no-such-definition/").status_code == 404
