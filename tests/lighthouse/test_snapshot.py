"""
Unit tests for the Snapshot model.

Covers:
  Snapshot.create_pages()    – Page objects are created from the site's URLs
  Snapshot.collect_metrics() – SnapshotCategory/SnapshotAudit rows are built
  Snapshot.delete_config_file() – temp file is deleted and field cleared
"""

import pathlib

import pytest

from lighthouse.models import SnapshotAudit, SnapshotCategory
from tests.factories import LighthouseSnapshotFactory, PageFactory, SiteFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sitemap(httpserver) -> bytes:
    """A small sitemap served by the local test HTTP server."""
    url1 = httpserver.url_for("/")
    url2 = httpserver.url_for("/about/")
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>{url1}</loc></url>
      <url><loc>{url2}</loc></url>
    </urlset>""".encode()
    httpserver.expect_request("/sitemap.xml").respond_with_data(
        xml, content_type="text/xml"
    )
    return xml


@pytest.fixture
def snapshot_with_config(tmp_path):
    """Snapshot whose config_file points to a real file on disk."""
    config_file = tmp_path / "lighthouse-config.json"
    config_file.write_text('{"formFactor": "desktop"}')
    return LighthouseSnapshotFactory(config_file=str(config_file))


@pytest.fixture
def audited_page(snapshot_with_config, lighthouse_report):
    """A Page that has been collect_metrics'd, creating PageCategory/PageAudit rows."""
    page = PageFactory(snapshot=snapshot_with_config, audited=True)
    page.collect_metrics(lighthouse_report)
    return page


# ---------------------------------------------------------------------------
# Snapshot.create_pages()
# ---------------------------------------------------------------------------


class TestSnapshotCreatePages:
    def test_creates_one_page_per_url(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = LighthouseSnapshotFactory(snapshot__site=site)
        snapshot.create_pages()
        assert snapshot.pages.count() == 2

    def test_pages_are_initially_not_audited(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = LighthouseSnapshotFactory(snapshot__site=site)
        snapshot.create_pages()
        assert snapshot.pages.filter(audited=False).count() == 2

    def test_page_urls_match_sitemap(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = LighthouseSnapshotFactory(snapshot__site=site)
        snapshot.create_pages()
        urls = set(snapshot.pages.values_list("url", flat=True))
        assert httpserver.url_for("/") in urls
        assert httpserver.url_for("/about/") in urls

    def test_calling_twice_does_not_duplicate_pages(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = LighthouseSnapshotFactory(snapshot__site=site)
        snapshot.create_pages()
        snapshot.create_pages()
        assert snapshot.pages.count() == 2


# ---------------------------------------------------------------------------
# Snapshot.collect_metrics()
# ---------------------------------------------------------------------------


class TestSnapshotCollectMetrics:
    def test_creates_snapshot_categories(self, snapshot_with_config, audited_page):
        snapshot_with_config.collect_metrics()
        assert SnapshotCategory.objects.filter(snapshot=snapshot_with_config).count() == 4

    def test_category_ids_are_correct(self, snapshot_with_config, audited_page):
        snapshot_with_config.collect_metrics()
        ids = set(
            SnapshotCategory.objects.filter(snapshot=snapshot_with_config)
            .values_list("category_id", flat=True)
        )
        assert ids == {"performance", "accessibility", "best-practices", "seo"}

    def test_creates_snapshot_audits(self, snapshot_with_config, audited_page):
        snapshot_with_config.collect_metrics()
        assert SnapshotAudit.objects.filter(snapshot=snapshot_with_config).count() > 0

    def test_good_count_reflects_page_ratings(self, snapshot_with_config, audited_page):
        # accessibility score 0.90 → GOOD
        snapshot_with_config.collect_metrics()
        acc = SnapshotCategory.objects.get(
            snapshot=snapshot_with_config, category_id="accessibility"
        )
        assert acc.good_count == 1
        assert acc.poor_count == 0

    def test_needs_improvement_count_reflects_page_ratings(
        self, snapshot_with_config, audited_page
    ):
        # performance score 0.85 → NEEDS_IMPROVEMENT
        snapshot_with_config.collect_metrics()
        perf = SnapshotCategory.objects.get(
            snapshot=snapshot_with_config, category_id="performance"
        )
        assert perf.needs_count == 1
        assert perf.poor_count == 0

    def test_aggregate_counts_across_multiple_pages(
        self, snapshot_with_config, lighthouse_report
    ):
        page1 = PageFactory(snapshot=snapshot_with_config, audited=True)
        page1.collect_metrics(lighthouse_report)
        page2 = PageFactory(snapshot=snapshot_with_config, audited=True)
        page2.collect_metrics(lighthouse_report)

        snapshot_with_config.collect_metrics()
        acc = SnapshotCategory.objects.get(
            snapshot=snapshot_with_config, category_id="accessibility"
        )
        # Both pages are GOOD → good_count == 2
        assert acc.good_count == 2

    def test_status_set_to_complete(self, snapshot_with_config, audited_page):
        from lighthouse.models import Snapshot
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        assert snapshot_with_config.status == Snapshot.Status.COMPLETE

    def test_page_count_set_after_collect(self, snapshot_with_config, audited_page):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        assert snapshot_with_config.page_count == 1

    def test_config_file_is_deleted_after_collect(
        self, snapshot_with_config, audited_page
    ):
        config_path = pathlib.Path(snapshot_with_config.config_file)
        assert config_path.exists()
        snapshot_with_config.collect_metrics()
        assert not config_path.exists()

    def test_config_file_field_cleared_after_collect(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        assert snapshot_with_config.config_file == ""

    def test_unaudited_pages_are_ignored(self, snapshot_with_config, lighthouse_report):
        audited = PageFactory(snapshot=snapshot_with_config, audited=True)
        audited.collect_metrics(lighthouse_report)
        PageFactory(snapshot=snapshot_with_config, audited=False)

        snapshot_with_config.collect_metrics()
        acc = SnapshotCategory.objects.get(
            snapshot=snapshot_with_config, category_id="accessibility"
        )
        assert acc.good_count == 1  # only the audited page

    def test_no_audited_pages_leaves_no_categories(self, snapshot_with_config):
        snapshot_with_config.collect_metrics()
        assert not SnapshotCategory.objects.filter(snapshot=snapshot_with_config).exists()


# ---------------------------------------------------------------------------
# Snapshot.delete_config_file()
# ---------------------------------------------------------------------------


class TestSnapshotDeleteConfigFile:
    def test_deletes_file_on_disk(self, snapshot_with_config):
        path = pathlib.Path(snapshot_with_config.config_file)
        assert path.exists()
        snapshot_with_config.delete_config_file()
        assert not path.exists()

    def test_clears_config_file_field(self, snapshot_with_config):
        snapshot_with_config.delete_config_file()
        snapshot_with_config.refresh_from_db()
        assert snapshot_with_config.config_file == ""

    def test_no_error_when_file_already_missing(self, snapshot_with_config):
        path = pathlib.Path(snapshot_with_config.config_file)
        path.unlink()
        snapshot_with_config.delete_config_file()  # should not raise
