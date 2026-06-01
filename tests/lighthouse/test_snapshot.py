"""
Unit tests for the lighthouse Run model.

Covers:
  Run.delete_config_file() – temp file is deleted and field cleared
  Run.complete()           – status, page_count, and parent scan are updated
"""

import pathlib

import pytest

from lighthouse.models import Run
from tests.factories import LighthouseRunFactory, PageFactory, SiteFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def run_with_config(tmp_path):
    """Run whose config_file points to a real file on disk."""
    config_file = tmp_path / "lighthouse-config.json"
    config_file.write_text('{"formFactor": "desktop"}')
    return LighthouseRunFactory(config_file=str(config_file))


# ---------------------------------------------------------------------------
# Run.delete_config_file()
# ---------------------------------------------------------------------------


class TestRunDeleteConfigFile:
    def test_deletes_file_on_disk(self, run_with_config):
        path = pathlib.Path(run_with_config.config_file)
        assert path.exists()
        run_with_config.delete_config_file()
        assert not path.exists()

    def test_clears_config_file_field(self, run_with_config):
        run_with_config.delete_config_file()
        run_with_config.refresh_from_db()
        assert run_with_config.config_file == ""

    def test_no_error_when_file_already_missing(self, run_with_config):
        path = pathlib.Path(run_with_config.config_file)
        path.unlink()
        run_with_config.delete_config_file()  # should not raise


# ---------------------------------------------------------------------------
# Run.complete()
# ---------------------------------------------------------------------------


class TestRunComplete:
    def test_sets_status_to_complete(self, run_with_config):
        run_with_config.complete()
        run_with_config.refresh_from_db()
        assert run_with_config.status == Run.Status.COMPLETE

    def test_sets_page_count(self, run_with_config):
        PageFactory(scan=run_with_config.scan)
        PageFactory(scan=run_with_config.scan)
        run_with_config.complete()
        run_with_config.refresh_from_db()
        assert run_with_config.page_count == 2

    def test_marks_parent_scan_complete(self, run_with_config):
        from sites.models import Scan
        run_with_config.complete()
        run_with_config.scan.refresh_from_db()
        assert run_with_config.scan.status == Scan.Status.COMPLETE

    def test_updates_site_current_scan(self, run_with_config):
        from sites.models import Site
        run_with_config.complete()
        site = Site.objects.get(pk=run_with_config.scan.site_id)
        assert site.current_scan_id == run_with_config.scan_id

    def test_config_file_deleted_after_complete(self, run_with_config):
        config_path = pathlib.Path(run_with_config.config_file)
        assert config_path.exists()
        run_with_config.complete()
        assert not config_path.exists()
