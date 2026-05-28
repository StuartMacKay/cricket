"""
Unit tests for the Page model.

Covers:
  Page.audit()                      – subprocess is mocked so Lighthouse never runs
  Page._collect_category_metrics()  – category score/rating/quantile extraction
  Page._collect_audit_metrics()     – per-audit type, score and value extraction
"""

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from metrics.models import Rating
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
def snapshot():
    """A snapshot with a (dummy) config_file path; the file doesn't need to
    exist on disk because subprocess.run is always mocked in these tests."""
    return SnapshotFactory(data={"config_file": "/tmp/test-lighthouse-config.json"})


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

    def test_successful_audit_populates_page_data(
        self, monkeypatch, page, lighthouse_report
    ):
        mock_subprocess_success(monkeypatch, lighthouse_report)
        page.audit()
        page.refresh_from_db()
        assert "categories" in page.data
        assert "audits" in page.data

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

    def test_subprocess_failure_marks_page_as_not_audited(
        self, monkeypatch, page
    ):
        mock_subprocess_failure(monkeypatch)
        page.audit()
        page.refresh_from_db()
        assert page.audited is False

    def test_subprocess_failure_saves_error_as_text_file(
        self, monkeypatch, page
    ):
        mock_subprocess_failure(monkeypatch, stderr=b"Chromium crashed")
        page.audit()
        page.refresh_from_db()
        assert page.report.name.endswith(".txt")


# ---------------------------------------------------------------------------
# Page._collect_category_metrics()
# ---------------------------------------------------------------------------


class TestPageCollectCategoryMetrics:
    """_collect_category_metrics transforms the raw LHR into per-category
    summaries and stores them in page.data['categories']."""

    def test_all_four_categories_are_extracted(self, page, lighthouse_report):
        page._collect_category_metrics(lighthouse_report)
        assert set(page.data["categories"]) == {
            "performance",
            "accessibility",
            "best-practices",
            "seo",
        }

    def test_required_keys_are_present_in_each_category(
        self, page, lighthouse_report
    ):
        page._collect_category_metrics(lighthouse_report)
        required = {"id", "title", "type", "score", "rating", "quantile", "audits"}
        for category in page.data["categories"].values():
            assert required <= category.keys()

    def test_score_is_scaled_from_fraction_to_integer(
        self, page, lighthouse_report
    ):
        # 0.85 → 85
        page._collect_category_metrics(lighthouse_report)
        assert page.data["categories"]["performance"]["score"] == 85

    def test_type_is_always_numeric(self, page, lighthouse_report):
        page._collect_category_metrics(lighthouse_report)
        for category in page.data["categories"].values():
            assert category["type"] == "numeric"

    def test_rating_poor_below_50(self, page, lighthouse_report):
        lighthouse_report["categories"]["performance"]["score"] = 0.40
        page._collect_category_metrics(lighthouse_report)
        assert page.data["categories"]["performance"]["rating"] == Rating.POOR

    def test_rating_needs_improvement_50_to_89(self, page, lighthouse_report):
        page._collect_category_metrics(lighthouse_report)
        # fixture score is 0.85 → 85 → NEEDS_IMPROVEMENT
        assert (
            page.data["categories"]["performance"]["rating"]
            == Rating.NEEDS_IMPROVEMENT
        )

    def test_rating_good_90_and_above(self, page, lighthouse_report):
        page._collect_category_metrics(lighthouse_report)
        # fixture accessibility score is 0.90 → 90 → GOOD
        assert page.data["categories"]["accessibility"]["rating"] == Rating.GOOD

    def test_quantile_is_score_divided_by_5(self, page, lighthouse_report):
        # score 85 → quantile 17 (int(85/5))
        page._collect_category_metrics(lighthouse_report)
        assert page.data["categories"]["performance"]["quantile"] == 17

    def test_perfect_score_gives_quantile_19(self, page, lighthouse_report):
        lighthouse_report["categories"]["performance"]["score"] = 1.0
        page._collect_category_metrics(lighthouse_report)
        assert page.data["categories"]["performance"]["quantile"] == 19

    def test_audit_ids_listed_from_audit_refs(self, page, lighthouse_report):
        page._collect_category_metrics(lighthouse_report)
        performance_audits = page.data["categories"]["performance"]["audits"]
        assert "first-contentful-paint" in performance_audits
        assert "total-blocking-time" in performance_audits


# ---------------------------------------------------------------------------
# Page._collect_audit_metrics()
# ---------------------------------------------------------------------------


class TestPageCollectAuditMetrics:
    """_collect_audit_metrics transforms raw LHR audits into the stored format.

    collect_metrics() calls _collect_category_metrics first and
    _collect_audit_metrics second, but _collect_audit_metrics reads directly
    from the LHR (not from page.data), so either order works for unit tests.
    """

    def test_all_audit_keys_are_extracted(self, page, lighthouse_report):
        page._collect_audit_metrics(lighthouse_report)
        assert set(page.data["audits"]) == set(lighthouse_report["audits"])

    def test_required_keys_present_in_each_audit(self, page, lighthouse_report):
        page._collect_audit_metrics(lighthouse_report)
        required = {"id", "title", "category", "weight", "type"}
        for audit in page.data["audits"].values():
            assert required <= audit.keys()

    def test_performance_audit_is_typed_numeric(self, page, lighthouse_report):
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["first-contentful-paint"]["type"] == "numeric"

    def test_non_performance_audit_is_typed_binary(self, page, lighthouse_report):
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["color-contrast"]["type"] == "binary"

    def test_numeric_score_is_scaled_to_integer(self, page, lighthouse_report):
        # raw 0.90 → 90
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["first-contentful-paint"]["score"] == 90

    def test_millisecond_value_is_rounded_to_integer(self, page, lighthouse_report):
        # numericValue 150.7 ms → 151
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["total-blocking-time"]["value"] == 151

    def test_quantile_is_score_divided_by_5_for_numeric_audit(
        self, page, lighthouse_report
    ):
        # score 90 → quantile 18
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["first-contentful-paint"]["quantile"] == 18

    def test_null_score_sets_type_to_none(self, page, lighthouse_report):
        lighthouse_report["audits"]["color-contrast"]["score"] = None
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["color-contrast"]["type"] is None

    def test_null_score_sets_score_to_zero(self, page, lighthouse_report):
        lighthouse_report["audits"]["color-contrast"]["score"] = None
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["color-contrast"]["score"] == 0

    def test_audit_is_assigned_to_correct_category(self, page, lighthouse_report):
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["color-contrast"]["category"] == "accessibility"
        assert page.data["audits"]["is-on-https"]["category"] == "best-practices"

    def test_weight_is_taken_from_audit_ref(self, page, lighthouse_report):
        page._collect_audit_metrics(lighthouse_report)
        assert page.data["audits"]["first-contentful-paint"]["weight"] == 10
        assert page.data["audits"]["largest-contentful-paint"]["weight"] == 25
