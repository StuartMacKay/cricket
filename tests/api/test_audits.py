"""Tests for the audit definitions endpoint."""

import pytest

from tests.factories import AuditDefinitionFactory, LighthousePageFactory, LighthouseRunFactory, PageAuditFactory, SiteFactory

pytestmark = pytest.mark.django_db


class TestListAudits:
    def test_requires_auth(self, client):
        assert client.get("/api/audits/").status_code == 401

    def test_returns_200(self, auth_client):
        assert auth_client.get("/api/audits/").status_code == 200

    def test_lists_audit_definitions(self, auth_client):
        AuditDefinitionFactory(audit_id="color-contrast", category_id="accessibility")
        AuditDefinitionFactory(audit_id="first-contentful-paint", category_id="performance")
        assert len(auth_client.get("/api/audits/").json()) == 2

    def test_has_failures_filter(self, auth_client):
        passing = AuditDefinitionFactory(audit_id="good-audit")
        failing = AuditDefinitionFactory(audit_id="bad-audit")
        site = SiteFactory()
        run  = LighthouseRunFactory(job__site=site)
        page = LighthousePageFactory(run=run)
        PageAuditFactory(page=page, audit=failing, rating="poor")
        data = auth_client.get("/api/audits/", {"has_failures": "true"}).json()
        ids = [a["audit_id"] for a in data]
        assert "bad-audit" in ids
        assert "good-audit" not in ids

    def test_invalid_sort_returns_422(self, auth_client):
        assert auth_client.get("/api/audits/", {"sort": "invalid"}).status_code == 422


class TestGetAudit:
    def test_returns_200(self, auth_client):
        AuditDefinitionFactory(audit_id="color-contrast")
        assert auth_client.get("/api/audits/color-contrast/").status_code == 200

    def test_returns_404_for_missing(self, auth_client):
        assert auth_client.get("/api/audits/no-such-audit/").status_code == 404
