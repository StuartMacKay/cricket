"""Shared fixtures for the audits test suite."""

from types import SimpleNamespace

import pytest
from audits.models import Run

from tests.factories import (
    AuditFactory,
    DefinitionFactory,
    JobFactory,
    MetricFactory,
    PageFactory,
    ReportFactory,
    RunFactory,
    SiteFactory,
)


@pytest.fixture
def complete_run(db):
    """A fully-populated completed run with one page, report, and metric."""
    site = SiteFactory()
    audit = AuditFactory(task="audits.tasks.page_headers")
    definition = DefinitionFactory(audit=audit)
    job = JobFactory(site=site, audits=[audit])
    run = RunFactory(
        job=job, status=Run.Status.COMPLETE, total_tasks=1, completed_tasks=1
    )
    page = PageFactory(site=site)
    report = ReportFactory(run=run, page=page, audit=audit)
    metric = MetricFactory(
        report=report, definition=definition, score=75, rating="needs-improvement"
    )

    return SimpleNamespace(
        site=site,
        audit=audit,
        definition=definition,
        job=job,
        run=run,
        page=page,
        report=report,
        metric=metric,
    )
