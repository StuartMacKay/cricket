"""Tests for the introspection endpoints."""

import pytest

pytestmark = pytest.mark.django_db


class TestApiRoot:
    def test_returns_200_without_auth(self, client):
        response = client.get("/api/")
        assert response.status_code == 200

    def test_response_contains_endpoints(self, client):
        response = client.get("/api/")
        data = response.json()
        assert "endpoints" in data
        assert "agent_context" in data["endpoints"]
        assert "schema" in data["endpoints"]


class TestAgentContext:
    def test_returns_200_without_auth(self, client):
        response = client.get("/api/agent-context/")
        assert response.status_code == 200

    def test_response_contains_schema_version(self, client):
        data = client.get("/api/agent-context/").json()
        assert data["schema_version"] == "2"

    def test_response_contains_static_resources(self, client):
        data = client.get("/api/agent-context/").json()
        assert "resources" in data
        assert "sites" in data["resources"]
        assert "audits" in data["resources"]
        assert "feedback" in data["resources"]

    def test_response_contains_filter_params(self, client):
        data = client.get("/api/agent-context/").json()
        assert "rating" in data["filter_params"]
        valid_ratings = data["filter_params"]["rating"]
        assert "poor" in valid_ratings
        assert "needs-improvement" in valid_ratings
        assert "good" in valid_ratings

    def test_response_contains_pagination(self, client):
        data = client.get("/api/agent-context/").json()
        assert "pagination" in data
        assert data["pagination"]["default_limit"] == 20

    def test_response_contains_notes(self, client):
        data = client.get("/api/agent-context/").json()
        assert "notes" in data
        assert any("scheduled" in note for note in data["notes"])

    def test_api_key_name_null_when_unauthenticated(self, client):
        data = client.get("/api/agent-context/").json()
        assert data["api_key_name"] is None

    def test_tool_context_auto_discovered(self, client):
        """A fake tool app with AGENT_CONTEXT should appear in resources."""
        import sys
        import types

        fake = types.ModuleType("fake_tool.api")
        fake.AGENT_CONTEXT = {
            "tool": "fake_tool",
            "runs": {"list": "GET /api/sites/{slug}/fake_tool/runs/"},
        }
        sys.modules["fake_tool.api"] = fake

        from django.conf import settings
        original = settings.INSTALLED_APPS
        settings.INSTALLED_APPS = list(original) + ["fake_tool"]
        try:
            data = client.get("/api/agent-context/").json()
            assert "fake_tool" in data["resources"]
            assert "runs" in data["resources"]["fake_tool"]
        finally:
            settings.INSTALLED_APPS = original
            del sys.modules["fake_tool.api"]
