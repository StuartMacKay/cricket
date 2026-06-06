"""Tests for the api pages endpoints."""

import pytest
from audits.models import Run

from tests.factories import (
    AuditFactory,
    DefinitionFactory,
    FindingFactory,
    JobFactory,
    MetricFactory,
    PageFactory,
    ReportFactory,
    RunFactory,
    SiteFactory,
)

pytestmark = pytest.mark.django_db


class TestListPages:
    def test_requires_auth(self, client):
        site = SiteFactory()
        assert client.get(f"/api/sites/{site.slug}/pages/").status_code == 401

    def test_returns_200(self, auth_client):
        site = SiteFactory()
        assert auth_client.get(f"/api/sites/{site.slug}/pages/").status_code == 200

    def test_returns_pages_for_site(self, auth_client):
        site = SiteFactory()
        PageFactory(site=site)
        PageFactory(site=site)
        data = auth_client.get(f"/api/sites/{site.slug}/pages/").json()
        assert data["count"] == 2

    def test_returns_404_for_missing_site(self, auth_client):
        assert auth_client.get("/api/sites/no-such-site/pages/").status_code == 404

    def test_pagination_fields_present(self, auth_client):
        site = SiteFactory()
        data = auth_client.get(f"/api/sites/{site.slug}/pages/").json()
        assert "items" in data
        assert "count" in data
        assert "truncated" in data


class TestGetPage:
    def test_returns_200_for_existing(self, auth_client):
        site = SiteFactory()
        page = PageFactory(site=site)
        assert (
            auth_client.get(f"/api/sites/{site.slug}/pages/{page.pk}/").status_code
            == 200
        )

    def test_returns_404_for_missing_page(self, auth_client):
        site = SiteFactory()
        assert (
            auth_client.get(f"/api/sites/{site.slug}/pages/99999/").status_code == 404
        )

    def test_returns_404_for_wrong_site(self, auth_client):
        site_a = SiteFactory()
        site_b = SiteFactory()
        page = PageFactory(site=site_b)
        assert (
            auth_client.get(f"/api/sites/{site_a.slug}/pages/{page.pk}/").status_code
            == 404
        )


class TestPageMetrics:
    def _setup(self):
        site = SiteFactory()
        audit = AuditFactory()
        definition = DefinitionFactory(audit=audit)
        page = PageFactory(site=site)
        return site, audit, definition, page

    def test_returns_empty_when_no_completed_runs(self, auth_client):
        site, audit, definition, page = self._setup()
        url = f"/api/sites/{site.slug}/pages/{page.pk}/metrics/"
        data = auth_client.get(url).json()
        assert data == []

    def test_returns_metrics_from_latest_complete_run(self, auth_client):
        site, audit, definition, page = self._setup()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job, status=Run.Status.COMPLETE)
        report = ReportFactory(run=run, page=page, audit=audit)
        MetricFactory(report=report, definition=definition, score=80, rating="good")
        url = f"/api/sites/{site.slug}/pages/{page.pk}/metrics/"
        data = auth_client.get(url).json()
        assert len(data) == 1
        assert data[0]["score"] == 80

    def test_metric_has_expected_fields(self, auth_client):
        site, audit, definition, page = self._setup()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job, status=Run.Status.COMPLETE)
        report = ReportFactory(run=run, page=page, audit=audit)
        MetricFactory(report=report, definition=definition, score=80, rating="good")
        url = f"/api/sites/{site.slug}/pages/{page.pk}/metrics/"
        m = auth_client.get(url).json()[0]
        assert "definition" in m
        assert "score" in m
        assert "rating" in m
        assert "run_id" in m
        assert "measured" in m

    def test_run_id_filter(self, auth_client):
        site, audit, definition, page = self._setup()
        job = JobFactory(site=site, audits=[audit])
        run = RunFactory(job=job, status=Run.Status.COMPLETE)
        report = ReportFactory(run=run, page=page, audit=audit)
        MetricFactory(report=report, definition=definition, score=80)
        url = f"/api/sites/{site.slug}/pages/{page.pk}/metrics/?run_id={run.pk}"
        data = auth_client.get(url).json()
        assert len(data) == 1
        assert data[0]["run_id"] == run.pk

    def test_audit_filter(self, auth_client):
        site = SiteFactory()
        audit1 = AuditFactory()
        audit2 = AuditFactory()
        definition1 = DefinitionFactory(audit=audit1)
        definition2 = DefinitionFactory(audit=audit2)
        page = PageFactory(site=site)
        job = JobFactory(site=site, audits=[audit1, audit2])
        run = RunFactory(job=job, status=Run.Status.COMPLETE)
        report1 = ReportFactory(run=run, page=page, audit=audit1)
        report2 = ReportFactory(run=run, page=page, audit=audit2)
        MetricFactory(report=report1, definition=definition1, score=70)
        MetricFactory(report=report2, definition=definition2, score=60)
        url = f"/api/sites/{site.slug}/pages/{page.pk}/metrics/?audit={audit1.slug}"
        data = auth_client.get(url).json()
        assert len(data) == 1
        assert data[0]["definition"]["audit"]["slug"] == audit1.slug

    def test_returns_404_for_missing_page(self, auth_client):
        site = SiteFactory()
        assert (
            auth_client.get(f"/api/sites/{site.slug}/pages/99999/metrics/").status_code
            == 404
        )


class TestPageMetricHistory:
    def _setup(self):
        site = SiteFactory()
        audit = AuditFactory()
        definition = DefinitionFactory(audit=audit)
        page = PageFactory(site=site)
        job = JobFactory(site=site, audits=[audit])
        return site, audit, definition, page, job

    def _url(self, site, page, **params):
        base = f"/api/sites/{site.slug}/pages/{page.pk}/metrics/history/"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            return f"{base}?{qs}"
        return base

    def test_returns_empty_when_no_metrics(self, auth_client):
        site, audit, definition, page, job = self._setup()
        assert auth_client.get(self._url(site, page)).json() == []

    def test_returns_metrics_across_runs(self, auth_client):
        site, audit, definition, page, job = self._setup()
        for score in [70, 80, 90]:
            run = RunFactory(job=job, status=Run.Status.COMPLETE)
            report = ReportFactory(run=run, page=page, audit=audit)
            MetricFactory(report=report, definition=definition, score=score)
        data = auth_client.get(self._url(site, page)).json()
        assert len(data) == 3

    def test_definition_filter(self, auth_client):
        site, audit, definition, page, job = self._setup()
        other_def = DefinitionFactory(audit=audit)
        run = RunFactory(job=job, status=Run.Status.COMPLETE)
        report = ReportFactory(run=run, page=page, audit=audit)
        MetricFactory(report=report, definition=definition, score=80)
        MetricFactory(report=report, definition=other_def, score=60)
        data = auth_client.get(self._url(site, page, definition=definition.slug)).json()
        assert len(data) == 1
        assert data[0]["definition"]["slug"] == definition.slug

    def test_excludes_incomplete_runs(self, auth_client):
        site, audit, definition, page, job = self._setup()
        run = RunFactory(job=job, status=Run.Status.RUNNING)
        report = ReportFactory(run=run, page=page, audit=audit)
        MetricFactory(report=report, definition=definition, score=80)
        data = auth_client.get(self._url(site, page)).json()
        assert data == []

    def test_returns_404_for_missing_page(self, auth_client):
        site = SiteFactory()
        assert auth_client.get(f"/api/sites/{site.slug}/pages/99999/metrics/history/").status_code == 404
