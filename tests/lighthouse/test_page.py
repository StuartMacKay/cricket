"""Tests for lighthouse.Page — audit subprocess and metric extraction."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lighthouse.models import AuditDefinition, PageAudit, PageCategory, Rating
from tests.factories import LighthousePageFactory, LighthouseRunFactory

pytestmark = pytest.mark.django_db


def mock_subprocess_success(monkeypatch, report: dict):
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(report).encode()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)


def mock_subprocess_failure(monkeypatch, stderr: bytes = b"Chromium error"):
    result = MagicMock()
    result.returncode = 1
    result.stderr = stderr
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)


@pytest.fixture
def run(tmp_path):
    config_file = tmp_path / "lighthouse-config.json"
    config_file.write_text("{}")
    return LighthouseRunFactory(config_file=str(config_file))


@pytest.fixture
def page(run):
    return LighthousePageFactory(run=run, audited=False)


class TestPageAudit:
    def test_successful_audit_marks_page_audited(self, monkeypatch, page, lighthouse_report):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.audited is True

    def test_successful_audit_saves_json_report(self, monkeypatch, page, lighthouse_report):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.report.name.endswith(".json")

    def test_successful_audit_creates_categories(self, monkeypatch, page, lighthouse_report):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        assert page.categories.count() == 4

    def test_runtime_error_marks_not_audited(self, monkeypatch, page, lighthouse_report):
        lighthouse_report["runtimeError"] = {"code": "FAILED", "message": "404"}
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.audited is False

    def test_subprocess_failure_marks_not_audited(self, monkeypatch, page):
        mock_subprocess_failure(monkeypatch)
        page.audit()
        page.refresh_from_db()
        assert page.audited is False


class TestCollectMetrics:
    def test_creates_page_categories(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        assert page.categories.count() == 4

    def test_category_ids_match_lhr(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        ids = set(page.categories.values_list("category_id", flat=True))
        assert ids == {"performance", "accessibility", "best-practices", "seo"}

    def test_score_scaled_from_fraction(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        assert page.categories.get(category_id="performance").score == 85

    def test_creates_audit_definitions(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        assert AuditDefinition.objects.count() > 0

    def test_creates_page_audits(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        assert page.audits.count() > 0

    def test_calling_twice_replaces_rows(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        n = page.categories.count()
        page.collect_metrics(lighthouse_report)
        assert page.categories.count() == n


class TestRating:
    def test_none_returns_none(self):    assert Rating.get_rating(None) is None
    def test_below_50_is_poor(self):     assert Rating.get_rating(49) == Rating.POOR
    def test_50_is_needs(self):          assert Rating.get_rating(50) == Rating.NEEDS_IMPROVEMENT
    def test_90_is_good(self):           assert Rating.get_rating(90) == Rating.GOOD
