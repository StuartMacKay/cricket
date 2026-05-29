"""
Unit tests for the Page model.

Covers:
  Page.audit()             – subprocess is mocked so Lighthouse never runs
  Page.collect_metrics()   – PageCategory and PageAudit rows are created
  Page._upsert_audit_definitions() – AuditDefinition lookup table is populated
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lighthouse.models import AuditDefinition, PageAudit, PageCategory, Rating
from tests.factories import PageFactory, SnapshotFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_subprocess_success(monkeypatch, report: dict):
    """Make subprocess.run return a zero exit code with *report* as stdout."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = json.dumps(report).encode()
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)


def mock_subprocess_failure(monkeypatch, stderr: bytes = b"Chromium error"):
    """Make subprocess.run return a non-zero exit code."""
    result = MagicMock()
    result.returncode = 1
    result.stderr = stderr
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: result)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def snapshot(tmp_path):
    """A snapshot with a real config file on disk."""
    config_file = tmp_path / "lighthouse-config.json"
    config_file.write_text("{}")
    return SnapshotFactory(config_file=str(config_file))


@pytest.fixture
def page(snapshot):
    return PageFactory(snapshot=snapshot, audited=False)


# ---------------------------------------------------------------------------
# Page.audit() – subprocess mocked
# ---------------------------------------------------------------------------


class TestPageAudit:
    def test_successful_audit_marks_page_as_audited(
        self, monkeypatch, page, lighthouse_report
    ):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.audited is True

    def test_successful_audit_saves_json_report_file(
        self, monkeypatch, page, lighthouse_report
    ):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.report.name.endswith(".json")

    def test_successful_audit_creates_page_categories(
        self, monkeypatch, page, lighthouse_report
    ):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.categories.count() == 4

    def test_successful_audit_creates_page_audits(
        self, monkeypatch, page, lighthouse_report
    ):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.audits.count() > 0

    def test_runtime_error_marks_page_as_not_audited(
        self, monkeypatch, page, lighthouse_report
    ):
        lighthouse_report["runtimeError"] = {
            "code": "FAILED_DOCUMENT_REQUEST",
            "message": "Received HTTP Error code: 404 for document request",
        }
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.audited is False

    def test_run_warnings_mark_page_as_not_audited(
        self, monkeypatch, page, lighthouse_report
    ):
        lighthouse_report["runWarnings"] = ["Page was unable to load correctly"]
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert page.audited is False

    def test_subprocess_failure_marks_page_as_not_audited(self, monkeypatch, page):
        mock_subprocess_failure(monkeypatch)
        page.audit()
        page.refresh_from_db()
        assert page.audited is False

    def test_subprocess_failure_saves_error_as_text_file(self, monkeypatch, page):
        mock_subprocess_failure(monkeypatch, stderr=b"Chromium crashed")
        page.audit()
        page.refresh_from_db()
        assert page.report.name.endswith(".txt")


# ---------------------------------------------------------------------------
# Page.collect_metrics() – verifying ORM row creation
# ---------------------------------------------------------------------------


class TestPageCollectMetrics:
    def test_creates_page_categories(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        assert page.categories.count() == 4

    def test_category_ids_match_lhr(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        ids = set(page.categories.values_list("category_id", flat=True))
        assert ids == {"performance", "accessibility", "best-practices", "seo"}

    def test_score_is_scaled_from_fraction(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        perf = page.categories.get(category_id="performance")
        assert perf.score == 85  # 0.85 * 100

    def test_rating_poor_below_50(self, page, lighthouse_report):
        lighthouse_report["categories"]["performance"]["score"] = 0.40
        page.collect_metrics(lighthouse_report)
        perf = page.categories.get(category_id="performance")
        assert perf.rating == Rating.POOR

    def test_rating_needs_improvement_50_to_89(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        perf = page.categories.get(category_id="performance")
        assert perf.rating == Rating.NEEDS_IMPROVEMENT

    def test_rating_good_90_and_above(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        acc = page.categories.get(category_id="accessibility")
        assert acc.rating == Rating.GOOD

    def test_creates_audit_definitions(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        assert AuditDefinition.objects.count() > 0

    def test_audit_definition_category_assigned(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        fcp = AuditDefinition.objects.get(audit_id="first-contentful-paint")
        assert fcp.category_id == "performance"

    def test_audit_definition_non_performance_category(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        contrast = AuditDefinition.objects.get(audit_id="color-contrast")
        assert contrast.category_id == "accessibility"

    def test_creates_page_audits(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        assert page.audits.count() > 0

    def test_numeric_audit_has_value(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        fcp = page.audits.select_related("audit").get(
            audit__audit_id="first-contentful-paint"
        )
        assert fcp.value == 1200  # rounded from 1200.0 ms

    def test_millisecond_value_is_rounded(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        tbt = page.audits.select_related("audit").get(
            audit__audit_id="total-blocking-time"
        )
        assert tbt.value == 151  # 150.7 rounded

    def test_binary_audit_has_no_value(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        contrast = page.audits.select_related("audit").get(
            audit__audit_id="color-contrast"
        )
        assert contrast.value is None

    def test_calling_twice_replaces_rows(self, page, lighthouse_report):
        page.collect_metrics(lighthouse_report)
        count_first = page.categories.count()
        page.collect_metrics(lighthouse_report)
        count_second = page.categories.count()
        assert count_first == count_second


# ---------------------------------------------------------------------------
# Rating helper
# ---------------------------------------------------------------------------


class TestRating:
    def test_none_score_returns_none(self):
        assert Rating.get_rating(None) is None

    def test_score_below_50_is_poor(self):
        assert Rating.get_rating(49) == Rating.POOR

    def test_score_50_is_needs_improvement(self):
        assert Rating.get_rating(50) == Rating.NEEDS_IMPROVEMENT

    def test_score_89_is_needs_improvement(self):
        assert Rating.get_rating(89) == Rating.NEEDS_IMPROVEMENT

    def test_score_90_is_good(self):
        assert Rating.get_rating(90) == Rating.GOOD

    def test_score_100_is_good(self):
        assert Rating.get_rating(100) == Rating.GOOD
