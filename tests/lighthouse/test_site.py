"""
Unit tests for the Site model and its manager.

Covers:
  SiteManager.overdue()   – which sites are due for a new snapshot
  Site.create_snapshot()  – snapshot creation and config-file handling
"""

import json
import os

import pytest
import time_machine
from django.utils import timezone

from lighthouse.models import Site, Snapshot
from tests.factories import SiteFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Site.objects.overdue()
# ---------------------------------------------------------------------------


class TestSiteManagerOverdue:
    def test_no_sites_returns_empty_list(self):
        assert Site.objects.overdue() == []

    def test_disabled_site_is_excluded(self):
        SiteFactory(enabled=False, crontab="0 * * * *")
        assert Site.objects.overdue() == []

    def test_site_without_crontab_is_excluded(self):
        # with_schedule() filters out sites whose crontab field is empty
        SiteFactory(crontab="", snapped=None)
        assert Site.objects.overdue() == []

    def test_never_snapped_site_is_always_overdue(self):
        site = SiteFactory(crontab="0 * * * *", snapped=None)
        assert site in Site.objects.overdue()

    def test_site_past_its_next_run_is_overdue(self):
        # snapped at midnight, hourly schedule → next run 01:00
        # checking at 02:30 → overdue
        with time_machine.travel("2024-01-01 00:00:00 UTC", tick=False):
            site = SiteFactory(crontab="0 * * * *", snapped=timezone.now())
        with time_machine.travel("2024-01-01 02:30:00 UTC", tick=False):
            result = Site.objects.overdue()
        assert site in result

    def test_site_before_its_next_run_is_not_overdue(self):
        # snapped at midnight, hourly schedule → next run 01:00
        # checking at 00:30 → not yet due
        with time_machine.travel("2024-01-01 00:00:00 UTC", tick=False):
            site = SiteFactory(crontab="0 * * * *", snapped=timezone.now())
        with time_machine.travel("2024-01-01 00:30:00 UTC", tick=False):
            result = Site.objects.overdue()
        assert site not in result

    def test_only_overdue_sites_are_returned(self):
        with time_machine.travel("2024-01-01 00:00:00 UTC", tick=False):
            due = SiteFactory(crontab="0 * * * *", snapped=timezone.now())
            not_due = SiteFactory(crontab="0 * * * *", snapped=timezone.now())

        with time_machine.travel("2024-01-01 02:00:00 UTC", tick=False):
            # Bring not_due up to date so it's no longer overdue
            not_due.snapped = timezone.now()
            not_due.save()
            result = Site.objects.overdue()

        assert due in result
        assert not_due not in result


# ---------------------------------------------------------------------------
# Site.create_snapshot()
# ---------------------------------------------------------------------------


class TestSiteCreateSnapshot:
    def test_returns_a_snapshot_instance(self):
        site = SiteFactory()
        assert isinstance(site.create_snapshot(), Snapshot)

    def test_snapshot_is_linked_to_the_site(self):
        site = SiteFactory()
        snapshot = site.create_snapshot()
        assert snapshot.site == site

    def test_snapshot_is_persisted_to_the_database(self):
        site = SiteFactory()
        snapshot = site.create_snapshot()
        assert Snapshot.objects.filter(pk=snapshot.pk).exists()

    def test_config_file_is_created_on_disk(self):
        site = SiteFactory(platform="mobile")
        snapshot = site.create_snapshot()
        assert os.path.exists(snapshot.config_file)

    def test_config_file_contains_form_factor(self):
        site = SiteFactory(platform="desktop")
        snapshot = site.create_snapshot()
        with open(snapshot.config_file) as fp:
            data = json.load(fp)
        assert data["formFactor"] == "desktop"

    def test_config_file_merges_extra_config(self):
        site = SiteFactory(platform="mobile", extra_config={"onlyCategories": ["performance"]})
        snapshot = site.create_snapshot()
        with open(snapshot.config_file) as fp:
            data = json.load(fp)
        assert data["formFactor"] == "mobile"
        assert data["onlyCategories"] == ["performance"]

    def test_site_snapped_timestamp_is_updated(self):
        site = SiteFactory(snapped=None)
        before = timezone.now()
        site.create_snapshot()
        site.refresh_from_db()
        assert site.snapped is not None
        assert site.snapped >= before

    def test_each_call_creates_a_new_snapshot(self):
        site = SiteFactory()
        site.create_snapshot()
        site.create_snapshot()
        assert site.snapshots.count() == 2

    def test_snapshot_platform_defaults_to_mobile(self):
        site = SiteFactory()
        snapshot = site.create_snapshot()
        assert snapshot.platform == "mobile"

    def test_snapshot_platform_reflects_site_platform(self):
        site = SiteFactory(platform="desktop")
        snapshot = site.create_snapshot()
        assert snapshot.platform == "desktop"

    def test_snapshot_status_is_pending(self):
        site = SiteFactory()
        snapshot = site.create_snapshot()
        assert snapshot.status == Snapshot.Status.PENDING
