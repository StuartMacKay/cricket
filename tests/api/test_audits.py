"""Tests for the audit definitions endpoints."""

import pytest

from tests.factories import AuditDefinitionFactory, PageAuditFactory, PageFactory, ScanFactory, SiteFactory

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

    def test_has_failures_filter_excludes_passing_audits(self, auth_client):
        passing = AuditDefinitionFactory(audit_id="good-audit")
        failing = AuditDefinitionFactory(audit_id="bad-audit")
        site = SiteFactory()
        scan = ScanFactory(site=site)
        page = PageFactory(scan=scan)
        PageAuditFactory(page=page, audit=failing, rating="poor")

        response = auth_client.get("/api/audits/", {"has_failures": "true"})
        ids = [a["audit_id"] for a in response.json()]
        assert "bad-audit" in ids
        assert "good-audit" not in ids

    def test_sort_by_audit_id_is_alphabetical(self, auth_client):
        AuditDefinitionFactory(audit_id="zzz-audit")
        AuditDefinitionFactory(audit_id="aaa-audit")
        data = auth_client.get("/api/audits/", {"sort": "audit_id"}).json()
        ids = [a["audit_id"] for a in data]
        assert ids == sorted(ids)

    def test_sort_by_fail_rate_descending(self, auth_client):
        high = AuditDefinitionFactory(audit_id="high-fail")
        low = AuditDefinitionFactory(audit_id="low-fail")
        site = SiteFactory()
        scan = ScanFactory(site=site)
        page1 = PageFactory(scan=scan)
        page2 = PageFactory(scan=scan)
        # high fails on 2 pages, low fails on 1 — fail_rate is higher for high
        PageAuditFactory(page=page1, audit=high, rating="poor")
        PageAuditFactory(page=page2, audit=high, rating="poor")
        PageAuditFactory(page=page1, audit=low, rating="poor")

        data = auth_client.get("/api/audits/", {"sort": "fail_rate"}).json()
        ids = [a["audit_id"] for a in data]
        assert ids.index("high-fail") < ids.index("low-fail")

    def test_invalid_sort_returns_422(self, auth_client):
        response = auth_client.get("/api/audits/", {"sort": "invalid"})
        assert response.status_code == 422


class TestGetAudit:
    def test_returns_200_for_existing_audit(self, auth_client):
        AuditDefinitionFactory(audit_id="color-contrast")
        response = auth_client.get("/api/audits/color-contrast/")
        assert response.status_code == 200

    def test_returns_404_for_missing_audit(self, auth_client):
        response = auth_client.get("/api/audits/no-such-audit/")
        assert response.status_code == 404
