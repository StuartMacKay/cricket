"""Tests for lighthouse.Run model."""

import pathlib

import pytest

from lighthouse.models import Run
from sites.models import Site
from tests.factories import LighthouseRunFactory, PageFactory, SiteFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def run_with_config(tmp_path):
    config_file = tmp_path / "lighthouse-config.json"
    config_file.write_text('{"formFactor": "desktop"}')
    return LighthouseRunFactory(config_file=str(config_file))


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
        pathlib.Path(run_with_config.config_file).unlink()
        run_with_config.delete_config_file()  # should not raise


class TestRunComplete:
    def test_sets_status_to_complete(self, run_with_config):
        run_with_config.complete()
        run_with_config.refresh_from_db()
        assert run_with_config.status == Run.Status.COMPLETE

    def test_sets_page_count(self, run_with_config):
        PageFactory(run=run_with_config)
        PageFactory(run=run_with_config)
        run_with_config.complete()
        run_with_config.refresh_from_db()
        assert run_with_config.page_count == 2

    def test_updates_job_last_run(self, run_with_config):
        assert run_with_config.job.last_run is None
        run_with_config.complete()
        run_with_config.job.refresh_from_db()
        assert run_with_config.job.last_run is not None

    def test_config_file_deleted_after_complete(self, run_with_config):
        config_path = pathlib.Path(run_with_config.config_file)
        assert config_path.exists()
        run_with_config.complete()
        assert not config_path.exists()
