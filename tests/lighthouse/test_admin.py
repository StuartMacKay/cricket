"""Tests for the lighthouse admin."""

from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model

from lighthouse.admin.job import JobAdmin
from lighthouse.admin.run import RunAdmin
from lighthouse.models import Job, Run
from sites.models import Site
from tests.factories import LighthouseJobFactory, LighthouseRunFactory, SiteFactory

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(username="admin", password="password", email="admin@example.com")


@pytest.fixture
def run_admin():
    return RunAdmin(Run, AdminSite())


@pytest.fixture
def job_admin():
    return JobAdmin(Job, AdminSite())


class TestJobAdminTriggerAction:
    def test_trigger_dispatches_celery_task(self, client, superuser):
        job = LighthouseJobFactory()
        client.force_login(superuser)
        with patch("lighthouse.models.job.Job.trigger_run") as mock_trigger:
            client.post(
                "/admin/lighthouse/job/",
                {"action": "trigger_run", "_selected_action": [job.pk]},
                follow=True,
            )
        mock_trigger.assert_called_once()


class TestRunAdminPermissions:
    def test_add_denied(self, rf, superuser, run_admin):
        request = rf.get("/admin/")
        request.user = superuser
        assert run_admin.has_add_permission(request) is False

    def test_change_denied(self, rf, superuser, run_admin):
        request = rf.get("/admin/")
        request.user = superuser
        assert run_admin.has_change_permission(request) is False

    def test_job_is_readonly(self, run_admin):
        assert "job" in run_admin.readonly_fields

    def test_status_is_readonly(self, run_admin):
        assert "status" in run_admin.readonly_fields
