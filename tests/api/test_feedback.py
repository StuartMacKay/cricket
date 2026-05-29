"""Tests for the feedback endpoint."""

import pytest

from api.models import APIFeedback

pytestmark = pytest.mark.django_db


class TestCreateFeedback:
    def test_requires_auth(self, client):
        response = client.post(
            "/api/feedback/",
            content_type="application/json",
            data={"message": "test"},
        )
        assert response.status_code == 401

    def test_creates_feedback(self, auth_client):
        response = auth_client.post(
            "/api/feedback/",
            content_type="application/json",
            data={"message": "The filter didn't work", "endpoint": "/api/sites/"},
        )
        assert response.status_code == 200
        assert APIFeedback.objects.count() == 1

    def test_response_contains_message(self, auth_client):
        response = auth_client.post(
            "/api/feedback/",
            content_type="application/json",
            data={"message": "Something broke"},
        )
        assert response.json()["message"] == "Something broke"


class TestListFeedback:
    def test_requires_admin_key(self, auth_client):
        response = auth_client.get("/api/feedback/")
        assert response.status_code == 403

    def test_admin_key_can_list(self, admin_auth_client):
        response = admin_auth_client.get("/api/feedback/")
        assert response.status_code == 200
