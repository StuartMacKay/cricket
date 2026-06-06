"""Tests for the api runs endpoints."""

import pytest
from audits.models import Run

from tests.factories import (
    AuditFactory,
    JobFactory,
    PageFactory,
    ReportFactory,
    RunFactory,
    SiteFactory,
)

pytestmark = pytest.mark.django_db


class TestListRuns:
    def test_requires_auth(self, client):
        site = SiteFactory()
        assert client.get(f"/api/sites/{site.slug}/runs/").status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        job = JobFactory(site=site)
        RunFactory(job=job)
        assert auth_client.get(f"/api/sites/{site.slug}/runs/").status_code == 200

    def test_status_filter(self, auth_client):
        site = SiteFactory()
        job = JobFactory(site=site)
        RunFactory(job=job, status=Run.Status.COMPLETE)
        RunFactory(job=job, status=Run.Status.RUNNING)
        data = auth_client.get(f"/api/sites/{site.slug}/runs/?status=complete").json()
        assert data["count"] == 1
        assert data["items"][0]["status"] == "complete"

    def test_pagination_present(self, auth_client):
        site = SiteFactory()
        data = auth_client.get(f"/api/sites/{site.slug}/runs/").json()
        assert "items" in data
        assert "count" in data
        assert "truncated" in data


class TestGetRun:
    def test_returns_200_for_existing(self, auth_client):
        site = SiteFactory()
        job = JobFactory(site=site)
        run = RunFactory(job=job)
        assert (
            auth_client.get(f"/api/sites/{site.slug}/runs/{run.pk}/").status_code == 200
        )

    def test_returns_404_for_wrong_site(self, auth_client):
        site_a = SiteFactory()
        site_b = SiteFactory()
        job = JobFactory(site=site_b)
        run = RunFactory(job=job)
        assert (
            auth_client.get(f"/api/sites/{site_a.slug}/runs/{run.pk}/").status_code
            == 404
        )


class TestListRunReports:
    def test_returns_200(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        page = PageFactory(site=site)
        ReportFactory(run=run, page=page, audit=audit)
        assert (
            auth_client.get(
                f"/api/sites/{site.slug}/runs/{run.pk}/reports/"
            ).status_code
            == 200
        )

    def test_report_fields(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        page = PageFactory(site=site)
        ReportFactory(run=run, page=page, audit=audit)
        data = auth_client.get(f"/api/sites/{site.slug}/runs/{run.pk}/reports/").json()
        report = data["items"][0]
        assert "audit" in report
        assert "slug" in report["audit"]
        assert "page_url" in report
        assert "error" in report

    def test_audit_filter(self, auth_client):
        site = SiteFactory()
        audit1 = AuditFactory()
        audit2 = AuditFactory()
        job = JobFactory(site=site, audits=[audit1, audit2])
        run = RunFactory(job=job)
        page = PageFactory(site=site)
        ReportFactory(run=run, page=page, audit=audit1)
        ReportFactory(run=run, page=page, audit=audit2)
        url = f"/api/sites/{site.slug}/runs/{run.pk}/reports/?audit={audit1.slug}"
        data = auth_client.get(url).json()
        assert data["count"] == 1
        assert data["items"][0]["audit"]["slug"] == audit1.slug


class TestGetReport:
    def test_returns_200(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        page = PageFactory(site=site)
        report = ReportFactory(run=run, page=page, audit=audit)
        url = f"/api/sites/{site.slug}/runs/{run.pk}/reports/{report.pk}/"
        assert auth_client.get(url).status_code == 200

    def test_detail_fields_present(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        page = PageFactory(site=site)
        report = ReportFactory(run=run, page=page, audit=audit)
        url = f"/api/sites/{site.slug}/runs/{run.pk}/reports/{report.pk}/"
        data = auth_client.get(url).json()
        assert "data" in data
        assert "json_report_url" in data
        assert "html_report_url" in data
        assert "audit" in data
        assert "page_url" in data

    def test_file_urls_null_when_no_file(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job)
        page = PageFactory(site=site)
        report = ReportFactory(run=run, page=page, audit=audit)
        url = f"/api/sites/{site.slug}/runs/{run.pk}/reports/{report.pk}/"
        data = auth_client.get(url).json()
        assert data["json_report_url"] is None
        assert data["html_report_url"] is None

    def test_returns_404_for_wrong_run(self, auth_client):
        site = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site, audits=[audit])
        run1 = RunFactory(job=job)
        run2 = RunFactory(job=job)
        page = PageFactory(site=site)
        report = ReportFactory(run=run1, page=page, audit=audit)
        url = f"/api/sites/{site.slug}/runs/{run2.pk}/reports/{report.pk}/"
        assert auth_client.get(url).status_code == 404

    def test_returns_404_for_wrong_site(self, auth_client):
        site_a = SiteFactory()
        site_b = SiteFactory()
        audit = AuditFactory()
        job = JobFactory(site=site_b, audits=[audit])
        run = RunFactory(job=job)
        page = PageFactory(site=site_b)
        report = ReportFactory(run=run, page=page, audit=audit)
        url = f"/api/sites/{site_a.slug}/runs/{run.pk}/reports/{report.pk}/"
        assert auth_client.get(url).status_code == 404
