"""
Unit tests for the Snapshot model.

Covers:
  Snapshot.create_pages()    – Page objects are created from the site's URLs
  Snapshot.collect_metrics() – aggregate metrics are built from audited Pages
"""

import pathlib

import pytest

from metrics.models import Page
from tests.factories import PageFactory, SiteFactory, SnapshotFactory

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
    """Snapshot whose data dict contains a real config file on disk, so
    _delete_config_file() can be tested."""
    config_file = tmp_path / "lighthouse-config.json"
    config_file.write_text('{"formFactor": "desktop"}')
    return SnapshotFactory(data={"config_file": str(config_file)})


@pytest.fixture
def audited_page(snapshot_with_config, page_data):
    """A Page with fully-processed data, linked to snapshot_with_config."""
    return PageFactory(
        snapshot=snapshot_with_config,
        audited=True,
        data=page_data,
    )


# ---------------------------------------------------------------------------
# Snapshot.create_pages()
# ---------------------------------------------------------------------------


class TestSnapshotCreatePages:
    def test_creates_one_page_per_url(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = SnapshotFactory(site=site)
        snapshot.create_pages()
        assert snapshot.pages.count() == 2

    def test_pages_are_initially_not_audited(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = SnapshotFactory(site=site)
        snapshot.create_pages()
        assert snapshot.pages.filter(audited=False).count() == 2

    def test_page_urls_match_sitemap(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = SnapshotFactory(site=site)
        snapshot.create_pages()
        urls = set(snapshot.pages.values_list("url", flat=True))
        assert httpserver.url_for("/") in urls
        assert httpserver.url_for("/about/") in urls

    def test_calling_twice_does_not_duplicate_pages(self, httpserver, sitemap):
        site = SiteFactory(sitemap_url=httpserver.url_for("/sitemap.xml"))
        snapshot = SnapshotFactory(site=site)
        snapshot.create_pages()
        snapshot.create_pages()
        # get_or_create deduplicates on (url, audited=False, snapshot)
        assert snapshot.pages.count() == 2


# ---------------------------------------------------------------------------
# Snapshot.collect_metrics()
# ---------------------------------------------------------------------------


class TestSnapshotCollectMetrics:
    def test_no_audited_pages_leaves_snapshot_data_empty(
        self, snapshot_with_config
    ):
        # No pages created at all → _collect_metadata returns False
        snapshot_with_config.collect_metrics()
        assert "categories" not in snapshot_with_config.data
        assert "audits" not in snapshot_with_config.data

    def test_categories_are_present_after_collect(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        assert "categories" in snapshot_with_config.data

    def test_audits_are_present_after_collect(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        assert "audits" in snapshot_with_config.data

    def test_category_metadata_copied_from_audited_page(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        categories = snapshot_with_config.data["categories"]
        assert set(categories) == {"performance", "accessibility", "best-practices", "seo"}
        assert categories["performance"]["title"] == "Performance"

    def test_category_has_ratings_quantiles_and_urls(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        for category in snapshot_with_config.data["categories"].values():
            assert "ratings" in category
            assert "quantiles" in category
            assert "urls" in category

    def test_performance_audit_has_ratings_and_quantiles(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        perf_audits = [
            a
            for a in snapshot_with_config.data["audits"].values()
            if a["category"] == "performance"
        ]
        for audit in perf_audits:
            assert "ratings" in audit
            assert "quantiles" in audit

    def test_non_performance_audit_has_scores(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        non_perf = [
            a
            for a in snapshot_with_config.data["audits"].values()
            if a["category"] != "performance"
        ]
        for audit in non_perf:
            assert "scores" in audit

    def test_ratings_reflect_page_data(self, snapshot_with_config, audited_page):
        # page_data has accessibility score=90 → rating=GOOD (index 2).
        # One page audited → ratings should be [0, 0, 1] (one GOOD result).
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        accessibility_ratings = snapshot_with_config.data["categories"][
            "accessibility"
        ]["ratings"]
        assert accessibility_ratings[2] == 1   # one GOOD page
        assert accessibility_ratings[0] == 0   # no POOR pages
        assert accessibility_ratings[1] == 0   # no NEEDS_IMPROVEMENT pages

    def test_config_file_is_deleted_after_collect(
        self, snapshot_with_config, audited_page
    ):
        config_path = pathlib.Path(snapshot_with_config.data["config_file"])
        assert config_path.exists()
        snapshot_with_config.collect_metrics()
        assert not config_path.exists()

    def test_config_file_key_removed_from_data(
        self, snapshot_with_config, audited_page
    ):
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        assert "config_file" not in snapshot_with_config.data

    def test_unaudited_pages_are_ignored(self, snapshot_with_config, page_data):
        # Create one audited page and one unaudited page; metrics should only
        # reflect the audited one.
        PageFactory(snapshot=snapshot_with_config, audited=True, data=page_data)
        PageFactory(snapshot=snapshot_with_config, audited=False)
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        # With one audited page, accessibility ratings[2] == 1
        assert (
            snapshot_with_config.data["categories"]["accessibility"]["ratings"][2]
            == 1
        )

    def test_aggregate_counts_across_multiple_pages(
        self, snapshot_with_config, page_data
    ):
        # Two audited pages → each category's ratings should sum to 2
        PageFactory(snapshot=snapshot_with_config, audited=True, data=page_data)
        PageFactory(snapshot=snapshot_with_config, audited=True, data=page_data)
        snapshot_with_config.collect_metrics()
        snapshot_with_config.refresh_from_db()
        # Both pages have accessibility=GOOD, so index 2 should be 2
        assert (
            sum(
                snapshot_with_config.data["categories"]["accessibility"]["ratings"]
            )
            == 2
        )
