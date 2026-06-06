"""Tests for findings endpoints: GET /pages/{id}/findings/ and POST /runs/{id}/reports/{id}/findings/."""

import pytest
from audits.models import Finding

from tests.factories import (
    AuditFactory,
    FindingFactory,
    JobFactory,
    PageFactory,
    ReportFactory,
    RunFactory,
    SiteFactory,
)

pytestmark = pytest.mark.django_db


class TestListPageFindings:
    def _url(self, site, page):
        return f"/api/sites/{site.slug}/pages/{page.pk}/findings/"

    def test_requires_auth(self, client):
        site = SiteFactory()
        page = PageFactory(site=site)
        assert client.get(self._url(site, page)).status_code == 401

    def test_returns_200_empty(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        resp = auth_client.get(self._url(site, page))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_findings(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        FindingFactory(page=page, report=report, type="dead-link", title="Broken link")
        data = auth_client.get(self._url(site, page)).json()
        assert len(data) == 1
        finding = data[0]
        assert finding["type"] == "dead-link"
        assert finding["title"] == "Broken link"
        assert "severity" in finding
        assert "page_url" in finding

    def test_type_filter(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        FindingFactory(page=page, report=report, type="dead-link")
        FindingFactory(page=page, report=report, type="large-image")
        data = auth_client.get(self._url(site, page) + "?type=dead-link").json()
        assert len(data) == 1
        assert data[0]["type"] == "dead-link"

    def test_severity_filter(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        FindingFactory(page=page, report=report, severity=Finding.Severity.ERROR)
        FindingFactory(page=page, report=report, severity=Finding.Severity.INFO)
        data = auth_client.get(self._url(site, page) + "?severity=error").json()
        assert len(data) == 1
        assert data[0]["severity"] == "error"

    def test_run_filter(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run1 = RunFactory(job=job)
        run2 = RunFactory(job=job)
        report1 = ReportFactory(run=run1, page=page, audit=audit)
        report2 = ReportFactory(run=run2, page=page, audit=audit)
        FindingFactory(page=page, report=report1)
        FindingFactory(page=page, report=report2)
        data = auth_client.get(self._url(site, page) + f"?run_id={run1.pk}").json()
        assert len(data) == 1

    def test_page_isolation(self, auth_client):
        site = SiteFactory()
        page_a = PageFactory(site=site)
        page_b = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page_b, audit=audit)
        FindingFactory(page=page_b, report=report)
        data = auth_client.get(self._url(site, page_a)).json()
        assert data == []

    def test_unknown_page_returns_404(self, auth_client):
        site = SiteFactory()
        assert auth_client.get(f"/api/sites/{site.slug}/pages/9999/findings/").status_code == 404


class TestCreateFinding:
    def _url(self, site, run, report):
        return f"/api/sites/{site.slug}/runs/{run.pk}/reports/{report.pk}/findings/"

    def _payload(self, **kwargs):
        return {
            "type": "dead-link",
            "title": "Broken navigation link",
            "description": "The link /old-page returns 404",
            "url": "https://example.com/old-page",
            "severity": "error",
            "source": "link-checker-agent",
            **kwargs,
        }

    def test_requires_auth(self, client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        resp = client.post(
            self._url(site, run, report),
            data=self._payload(),
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_creates_finding_returns_201(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        resp = auth_client.post(
            self._url(site, run, report),
            data=self._payload(),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "dead-link"
        assert data["title"] == "Broken navigation link"
        assert data["severity"] == "error"
        assert data["source"] == "link-checker-agent"
        assert data["page_url"] == page.url
        assert data["report_id"] == report.pk

    def test_page_derived_from_report(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        auth_client.post(
            self._url(site, run, report),
            data=self._payload(),
            content_type="application/json",
        )
        assert Finding.objects.filter(page=page, report=report).count() == 1

    def test_minimal_payload_defaults(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        resp = auth_client.post(
            self._url(site, run, report),
            data={"type": "slow-lcp", "title": "LCP too slow"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "warning"
        assert data["source"] == ""
        assert data["description"] == ""

    def test_unknown_report_returns_404(self, auth_client):
        site = SiteFactory()
        job = JobFactory(site=site)
        run = RunFactory(job=job)
        resp = auth_client.post(
            f"/api/sites/{site.slug}/runs/{run.pk}/reports/9999/findings/",
            data=self._payload(),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_wrong_site_returns_404(self, auth_client):
        site_a = SiteFactory()
        site_b = SiteFactory()
        page = PageFactory(site=site_b)
        audit = AuditFactory()
        job = JobFactory(site=site_b, audits=[audit])
        run = RunFactory(job=job)
        report = ReportFactory(run=run, page=page, audit=audit)
        resp = auth_client.post(
            f"/api/sites/{site_a.slug}/runs/{run.pk}/reports/{report.pk}/findings/",
            data=self._payload(),
            content_type="application/json",
        )
        assert resp.status_code == 404
