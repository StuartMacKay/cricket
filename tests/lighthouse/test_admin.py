"""
Unit tests for the lighthouse admin.
"""

from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from lighthouse.admin.run import RunAdmin
from lighthouse.models import Run as LighthouseRun
from sites.admin.site import SiteAdmin
from sites.models import Site
from tests.factories import LighthouseRunFactory, SiteFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


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
def run_admin():
    return RunAdmin(LighthouseRun, AdminSite())


class TestCreateScanAction:
    def test_dispatches_task_for_each_selected_site(self, client, superuser):
        site1 = SiteFactory()
        site2 = SiteFactory()
        client.force_login(superuser)

        with patch("sites.admin.site.take_site_scan") as mock_task:
            client.post(
                "/admin/sites/site/",
                {
                    "action": "trigger_scan",
                    "_selected_action": [site1.pk, site2.pk],
                },
                follow=True,
            )

        assert mock_task.delay.call_count == 2
        called_pks = {call.args[0] for call in mock_task.delay.call_args_list}
        assert called_pks == {site1.pk, site2.pk}

    def test_adds_info_message_per_site(self, client, superuser):
        site = SiteFactory()
        client.force_login(superuser)

        with patch("sites.admin.site.take_site_scan"):
            response = client.post(
                "/admin/sites/site/",
                {
                    "action": "trigger_scan",
                    "_selected_action": [site.pk],
                },
                follow=True,
            )

        messages = list(response.context["messages"])
        assert any(site.name in str(m) for m in messages)


class TestRunAdminPermissions:
    def test_add_permission_is_denied(self, rf, superuser, run_admin):
        request = rf.get("/admin/")
        request.user = superuser
        assert run_admin.has_add_permission(request) is False

    def test_scan_is_readonly(self, run_admin):
        assert "scan" in run_admin.readonly_fields

    def test_created_is_readonly(self, run_admin):
        assert "created" in run_admin.readonly_fields

    def test_status_is_readonly(self, run_admin):
        assert "status" in run_admin.readonly_fields
