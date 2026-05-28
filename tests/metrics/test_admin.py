"""
Unit tests for the metrics admin.

Covers:
  SiteAdmin.create_snapshot  – admin action dispatches take_snapshot task
  SnapshotAdmin              – add permission is denied; readonly fields enforced
"""

from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from metrics.admin.site import SiteAdmin
from metrics.admin.snapshot import SnapshotAdmin
from metrics.models import Site, Snapshot
from tests.factories import SiteFactory, SnapshotFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin", password="password", email="admin@example.com"
    )


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def site_admin():
    return SiteAdmin(Site, AdminSite())


@pytest.fixture
def snapshot_admin():
    return SnapshotAdmin(Snapshot, AdminSite())


# ---------------------------------------------------------------------------
# SiteAdmin.create_snapshot action
# ---------------------------------------------------------------------------


class TestCreateSnapshotAction:
    def test_dispatches_task_for_each_selected_site(self, client, superuser):
        """Use the test client so messages middleware is available."""
        site1 = SiteFactory()
        site2 = SiteFactory()
        client.force_login(superuser)

        with patch("metrics.admin.site.take_snapshot") as mock_task:
            client.post(
                "/admin/metrics/site/",
                {
                    "action": "create_snapshot",
                    "_selected_action": [site1.pk, site2.pk],
                },
                follow=True,
            )

        assert mock_task.delay.call_count == 2
        called_pks = {call.args[0] for call in mock_task.delay.call_args_list}
        assert called_pks == {site1.pk, site2.pk}

    def test_adds_info_message_per_site(self, client, superuser):
        """Use the full test client so the messages middleware is active."""
        site = SiteFactory()
        client.force_login(superuser)

        with patch("metrics.admin.site.take_snapshot"):
            response = client.post(
                "/admin/metrics/site/",
                {
                    "action": "create_snapshot",
                    "_selected_action": [site.pk],
                },
                follow=True,
            )

        messages = list(response.context["messages"])
        assert any(site.name in str(m) for m in messages)


# ---------------------------------------------------------------------------
# SnapshotAdmin permissions
# ---------------------------------------------------------------------------


class TestSnapshotAdminPermissions:
    def test_add_permission_is_denied(self, rf, superuser, snapshot_admin):
        request = rf.get("/admin/")
        request.user = superuser
        assert snapshot_admin.has_add_permission(request) is False

    def test_site_is_readonly(self, snapshot_admin):
        assert "site" in snapshot_admin.readonly_fields

    def test_created_is_readonly(self, snapshot_admin):
        assert "created" in snapshot_admin.readonly_fields

    def test_modified_is_readonly(self, snapshot_admin):
        assert "modified" in snapshot_admin.readonly_fields
