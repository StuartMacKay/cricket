from unittest.mock import MagicMock, patch

import pytest
from audits.models import Run
from audits.tasks import audit_page, job_run

from tests.factories import (
    AuditFactory,
    JobFactory,
    PageFactory,
    RunFactory,
)

pytestmark = pytest.mark.django_db


class TestJobRun:
    def test_creates_a_run(self):
        audit = AuditFactory()
        job = JobFactory(urls="https://example.com/", audits=[audit])
        with patch("audits.tasks.audit_page.delay"):
            job_run(job.pk)
        assert Run.objects.filter(job=job).count() == 1

    def test_sets_total_tasks(self):
        audit1 = AuditFactory()
        audit2 = AuditFactory()
        job = JobFactory(
            urls="https://example.com/\nhttps://example.com/about/",
            audits=[audit1, audit2],
        )
        with patch("audits.tasks.audit_page.delay"):
            job_run(job.pk)
        run = Run.objects.get(job=job)
        assert run.total_tasks == 4

    def test_dispatches_audit_page_for_each_pair(self):
        audit = AuditFactory()
        job = JobFactory(
            urls="https://example.com/\nhttps://example.com/about/",
            audits=[audit],
        )
        with patch("audits.tasks.audit_page.delay") as mock_delay:
            job_run(job.pk)
        assert mock_delay.call_count == 2


class TestAuditPage:
    def test_calls_audit_task_function(self):
        audit = AuditFactory(task="audits.tasks.page_headers")
        page = PageFactory()
        run = RunFactory(total_tasks=1, completed_tasks=0)
        mock_task = MagicMock()

        with patch.dict("audits.tasks.current_app.tasks", {audit.task: mock_task}):
            audit_page(run.pk, audit.pk, page.pk)

        mock_task.assert_called_once_with(run.pk, audit.pk, page.pk)

    def test_calls_task_complete_after_audit(self):
        audit = AuditFactory(task="audits.tasks.page_headers")
        page = PageFactory()
        run = RunFactory(total_tasks=1, completed_tasks=0)
        mock_task = MagicMock()

        with patch.dict("audits.tasks.current_app.tasks", {audit.task: mock_task}):
            audit_page(run.pk, audit.pk, page.pk)

        run.refresh_from_db()
        assert run.completed_tasks == 1
        assert run.status == Run.Status.COMPLETE
