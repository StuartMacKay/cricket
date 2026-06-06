"""Tests for the api site-level metrics endpoint (rank pages by metric value)."""

import pytest
from audits.models import Run

from tests.factories import (
    AuditFactory,
    DefinitionFactory,
    JobFactory,
    MetricFactory,
    PageFactory,
    ReportFactory,
    RunFactory,
    SiteFactory,
)

pytestmark = pytest.mark.django_db


def _make_site_with_definition():
    """Return (site, audit, definition, job) ready for adding pages and runs."""
    site = SiteFactory()
    audit = AuditFactory()
    definition = DefinitionFactory(audit=audit)
    job = JobFactory(site=site, audits=[audit])
    return site, audit, definition, job


def _complete_run(job):
    return RunFactory(job=job, status=Run.Status.COMPLETE)


def _metric_for_page(run, page, audit, definition, score=None, value=None):
    report = ReportFactory(run=run, page=page, audit=audit)
    return MetricFactory(report=report, definition=definition, score=score, value=value)


class TestRequiresAuth:
    def test_requires_auth(self, client):
        site = SiteFactory()
        definition = DefinitionFactory()
        assert (
            client.get(
                f"/api/sites/{site.slug}/metrics/?definition={definition.slug}"
            ).status_code
            == 401
        )


class TestReturnsEmptyWhenNoData:
    def test_returns_empty_when_no_data(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}"
        data = auth_client.get(url).json()
        assert data == []


class TestReturnsMetricsForEachPage:
    def test_returns_metrics_for_each_page(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        for i in range(3):
            page = PageFactory(site=site)
            _metric_for_page(run, page, audit, definition, score=50 + i * 10)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}"
        data = auth_client.get(url).json()
        assert len(data) == 3


class TestDefaultOrderIsScoreAsc:
    def test_default_order_is_score_asc(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        page_a = PageFactory(site=site)
        page_b = PageFactory(site=site)
        page_c = PageFactory(site=site)
        _metric_for_page(run, page_a, audit, definition, score=80)
        _metric_for_page(run, page_b, audit, definition, score=40)
        _metric_for_page(run, page_c, audit, definition, score=60)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}"
        scores = [m["score"] for m in auth_client.get(url).json()]
        assert scores == [40, 60, 80]


class TestScoreDescOrder:
    def test_score_desc_order(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        page_a = PageFactory(site=site)
        page_b = PageFactory(site=site)
        _metric_for_page(run, page_a, audit, definition, score=30)
        _metric_for_page(run, page_b, audit, definition, score=70)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}&order=score_desc"
        scores = [m["score"] for m in auth_client.get(url).json()]
        assert scores == [70, 30]


class TestValueAscOrder:
    def test_value_asc_order(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        page_a = PageFactory(site=site)
        page_b = PageFactory(site=site)
        _metric_for_page(run, page_a, audit, definition, value=500.0)
        _metric_for_page(run, page_b, audit, definition, value=100.0)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}&order=value_asc"
        values = [m["value"] for m in auth_client.get(url).json()]
        assert values == [100.0, 500.0]


class TestValueDescOrder:
    def test_value_desc_order(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        page_a = PageFactory(site=site)
        page_b = PageFactory(site=site)
        _metric_for_page(run, page_a, audit, definition, value=500.0)
        _metric_for_page(run, page_b, audit, definition, value=100.0)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}&order=value_desc"
        values = [m["value"] for m in auth_client.get(url).json()]
        assert values == [500.0, 100.0]


class TestLimitParameter:
    def test_limit_parameter(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        for i in range(5):
            page = PageFactory(site=site)
            _metric_for_page(run, page, audit, definition, score=i * 10)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}&limit=1"
        data = auth_client.get(url).json()
        assert len(data) == 1


class TestOnlyLatestRunPerPage:
    def test_only_latest_run_per_page(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        page = PageFactory(site=site)
        run1 = _complete_run(job)
        run2 = _complete_run(job)
        _metric_for_page(run1, page, audit, definition, score=40)
        _metric_for_page(run2, page, audit, definition, score=90)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}"
        data = auth_client.get(url).json()
        assert len(data) == 1
        assert data[0]["score"] == 90
        assert data[0]["run_id"] == run2.pk


class TestOnlyCompleteRunsIncluded:
    def test_only_complete_runs_included(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        page = PageFactory(site=site)
        active_run = RunFactory(job=job, status=Run.Status.RUNNING)
        report = ReportFactory(run=active_run, page=page, audit=audit)
        MetricFactory(report=report, definition=definition, score=55)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}"
        data = auth_client.get(url).json()
        assert data == []


class TestMissingSiteReturns404:
    def test_missing_site_returns_404(self, auth_client):
        definition = DefinitionFactory()
        assert (
            auth_client.get(
                f"/api/sites/no-such-site/metrics/?definition={definition.slug}"
            ).status_code
            == 404
        )


class TestMissingDefinitionReturns404:
    def test_missing_definition_returns_404(self, auth_client):
        site = SiteFactory()
        assert (
            auth_client.get(
                f"/api/sites/{site.slug}/metrics/?definition=no-such-definition"
            ).status_code
            == 404
        )


class TestInvalidOrderReturns422:
    def test_invalid_order_returns_422(self, auth_client):
        site = SiteFactory()
        definition = DefinitionFactory()
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}&order=bad_order"
        assert auth_client.get(url).status_code == 422


class TestNullScoresSortLast:
    def test_null_scores_sort_last_in_asc(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        page_a = PageFactory(site=site)
        page_b = PageFactory(site=site)
        page_c = PageFactory(site=site)
        _metric_for_page(run, page_a, audit, definition, score=None)
        _metric_for_page(run, page_b, audit, definition, score=80)
        _metric_for_page(run, page_c, audit, definition, score=30)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}&order=score_asc"
        data = auth_client.get(url).json()
        scores = [m["score"] for m in data]
        assert scores[-1] is None
        assert scores[0] == 30

    def test_null_scores_sort_last_in_desc(self, auth_client):
        site, audit, definition, job = _make_site_with_definition()
        run = _complete_run(job)
        page_a = PageFactory(site=site)
        page_b = PageFactory(site=site)
        page_c = PageFactory(site=site)
        _metric_for_page(run, page_a, audit, definition, score=None)
        _metric_for_page(run, page_b, audit, definition, score=80)
        _metric_for_page(run, page_c, audit, definition, score=30)
        url = f"/api/sites/{site.slug}/metrics/?definition={definition.slug}&order=score_desc"
        data = auth_client.get(url).json()
        scores = [m["score"] for m in data]
        assert scores[-1] is None
        assert scores[0] == 80
