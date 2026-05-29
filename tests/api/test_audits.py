"""Tests for the audit definitions endpoints."""

import pytest

from tests.factories import AuditDefinitionFactory

pytestmark = pytest.mark.django_db


class TestListAudits:
    def test_requires_auth(self, client):
        response = client.get("/api/audits/")
        assert response.status_code == 401

    def test_returns_200(self, auth_client):
        response = auth_client.get("/api/audits/")
        assert response.status_code == 200

    def test_lists_all_audit_definitions(self, auth_client):
        AuditDefinitionFactory(audit_id="color-contrast", category_id="accessibility")
        AuditDefinitionFactory(audit_id="first-contentful-paint", category_id="performance")
        response = auth_client.get("/api/audits/")
        assert len(response.json()) == 2

    def test_audit_fields_present(self, auth_client):
        AuditDefinitionFactory(audit_id="color-contrast", category_id="accessibility")
        data = auth_client.get("/api/audits/").json()
        audit = data[0]
        assert "audit_id" in audit
        assert "category_id" in audit
        assert "title" in audit
        assert "description" in audit


class TestGetAudit:
    def test_returns_200_for_existing_audit(self, auth_client):
        AuditDefinitionFactory(audit_id="color-contrast")
        response = auth_client.get("/api/audits/color-contrast/")
        assert response.status_code == 200

    def test_returns_404_for_missing_audit(self, auth_client):
        response = auth_client.get("/api/audits/no-such-audit/")
        assert response.status_code == 404
