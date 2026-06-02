"""Tests for the Site model and BaseJob.is_overdue()."""

import pytest
import time_machine
from django.utils import timezone

from sites.models import Site
from tests.factories import LighthouseJobFactory, SiteFactory

pytestmark = pytest.mark.django_db


class TestSite:
    def test_slug_auto_generated_from_name(self):
        site = Site.objects.create(name="My Site", primary_url="https://example.com")
        assert site.slug == "my-site"

    def test_slug_not_overwritten_if_set(self):
        site = Site.objects.create(name="My Site", slug="custom", primary_url="https://example.com")
        assert site.slug == "custom"

    def test_str_returns_name(self):
        site = SiteFactory(name="Acme Corp")
        assert str(site) == "Acme Corp"


class TestBaseJobIsOverdue:
    def test_no_crontab_is_never_overdue(self):
        job = LighthouseJobFactory(crontab="")
        assert job.is_overdue() is False

    def test_never_run_is_overdue(self):
        job = LighthouseJobFactory(crontab="0 * * * *", last_run=None)
        assert job.is_overdue() is True

    def test_past_due_is_overdue(self):
        with time_machine.travel("2024-01-01 00:00:00 UTC", tick=False):
            job = LighthouseJobFactory(crontab="0 * * * *", last_run=timezone.now())
        with time_machine.travel("2024-01-01 02:30:00 UTC", tick=False):
            assert job.is_overdue() is True

    def test_not_yet_due_is_not_overdue(self):
        with time_machine.travel("2024-01-01 00:00:00 UTC", tick=False):
            job = LighthouseJobFactory(crontab="0 * * * *", last_run=timezone.now())
        with time_machine.travel("2024-01-01 00:30:00 UTC", tick=False):
            assert job.is_overdue() is False
