import pytest
from audits.models import Rating, Run
from django.utils import timezone

from tests.factories import (
    JobFactory,
    PageFactory,
    ReportFactory,
    RunFactory,
)

pytestmark = pytest.mark.django_db


class TestRating:
    def test_good_at_90(self):
        assert Rating.get_rating(90) == Rating.GOOD

    def test_good_above_90(self):
        assert Rating.get_rating(100) == Rating.GOOD

    def test_needs_improvement_at_89(self):
        assert Rating.get_rating(89) == Rating.NEEDS_IMPROVEMENT

    def test_needs_improvement_at_50(self):
        assert Rating.get_rating(50) == Rating.NEEDS_IMPROVEMENT

    def test_poor_at_49(self):
        assert Rating.get_rating(49) == Rating.POOR

    def test_poor_at_0(self):
        assert Rating.get_rating(0) == Rating.POOR

    def test_none_returns_none(self):
        assert Rating.get_rating(None) is None


class TestRunComplete:
    def test_sets_status_complete(self):
        run = RunFactory(status=Run.Status.RUNNING)
        run.complete()
        run.refresh_from_db()
        assert run.status == Run.Status.COMPLETE

    def test_sets_page_count_from_distinct_pages(self):
        run = RunFactory(status=Run.Status.RUNNING)
        page_a = PageFactory(site=run.job.site)
        page_b = PageFactory(site=run.job.site)
        audit = (
            run.job.audits.first()
            or __import__("tests.factories", fromlist=["AuditFactory"]).AuditFactory()
        )
        ReportFactory(run=run, page=page_a, audit=audit)
        ReportFactory(run=run, page=page_a, audit=audit)
        ReportFactory(run=run, page=page_b, audit=audit)
        run.complete()
        run.refresh_from_db()
        assert run.page_count == 2

    def test_updates_job_executed(self):
        run = RunFactory(status=Run.Status.RUNNING)
        assert run.job.executed is None
        run.complete()
        run.job.refresh_from_db()
        assert run.job.executed is not None


class TestRunTaskComplete:
    def test_increments_completed_tasks(self):
        run = RunFactory(total_tasks=3, completed_tasks=0)
        run.task_complete()
        run.refresh_from_db()
        assert run.completed_tasks == 1

    def test_does_not_mark_complete_when_tasks_remain(self):
        run = RunFactory(total_tasks=3, completed_tasks=0)
        run.task_complete()
        run.refresh_from_db()
        assert run.status == Run.Status.RUNNING

    def test_marks_complete_when_last_task_finishes(self):
        run = RunFactory(total_tasks=1, completed_tasks=0)
        run.task_complete()
        run.refresh_from_db()
        assert run.status == Run.Status.COMPLETE

    def test_updates_job_executed_when_complete(self):
        run = RunFactory(total_tasks=1, completed_tasks=0)
        assert run.job.executed is None
        run.task_complete()
        run.job.refresh_from_db()
        assert run.job.executed is not None

    def test_complete_twice_does_not_corrupt_page_count(self):
        run = RunFactory(total_tasks=1, completed_tasks=0)
        page = PageFactory(site=run.job.site)
        from tests.factories import AuditFactory, ReportFactory

        audit = AuditFactory()
        ReportFactory(run=run, page=page, audit=audit)
        run.complete()
        run.complete()
        run.refresh_from_db()
        assert run.page_count == 1


class TestJobIsOverdue:
    def test_no_schedule_never_overdue(self):
        job = JobFactory(schedule="")
        assert job.is_overdue(timezone.now()) is False

    def test_has_schedule_never_executed_is_overdue(self):
        job = JobFactory(schedule="0 * * * *", executed=None)
        assert job.is_overdue(timezone.now()) is True

    def test_executed_recently_with_daily_schedule_not_overdue(self):
        from datetime import timedelta

        now = timezone.now()
        executed = now - timedelta(hours=1)
        # "0 0 * * *" fires once a day at midnight; 1 hour after last run is not overdue
        job = JobFactory(schedule="0 0 * * *", executed=executed)
        assert job.is_overdue(now) is False

    def test_executed_2_days_ago_with_daily_schedule_is_overdue(self):
        from datetime import timedelta

        now = timezone.now()
        executed = now - timedelta(days=2)
        job = JobFactory(schedule="0 0 * * *", executed=executed)
        assert job.is_overdue(now) is True
