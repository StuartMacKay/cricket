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
        assert data["schema_version"] == "1"

    def test_response_contains_resources(self, client):
        data = client.get("/api/agent-context/").json()
        assert "resources" in data
        assert "sites" in data["resources"]
        assert "snapshots" in data["resources"]
        assert "pages" in data["resources"]

    def test_response_contains_filter_params(self, client):
        data = client.get("/api/agent-context/").json()
        assert "rating" in data["filter_params"]
        valid_ratings = data["filter_params"]["rating"]
        assert "poor" in valid_ratings
        assert "needs-improvement" in valid_ratings
        assert "good" in valid_ratings

    def test_api_key_name_null_when_unauthenticated(self, client):
        data = client.get("/api/agent-context/").json()
        assert data["api_key_name"] is None
