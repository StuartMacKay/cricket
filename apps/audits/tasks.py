from celery import current_app, shared_task


@shared_task
def overdue_jobs():
    from .models import Job

    for job in Job.objects.overdue():
        job_run.delay(job.pk)


@shared_task
def job_run(job_pk):
    from .models import Job, Run

    job = Job.objects.get(pk=job_pk)
    pairs = [
        (audit.pk, page.pk) for audit in job.audits.all() for page in job.get_pages()
    ]
    run = Run.objects.create(job=job, total_tasks=len(pairs))

    for audit_pk, page_pk in pairs:
        audit_page.delay(run.pk, audit_pk, page_pk)


@shared_task
def audit_page(run_pk, audit_pk, page_pk):
    from .models import Audit, Run

    audit = Audit.objects.get(pk=audit_pk)
    current_app.tasks[audit.task](run_pk, audit_pk, page_pk)

    Run.objects.get(pk=run_pk).task_complete()


@shared_task
def page_headers(run_pk: int, audit_pk: int, page_pk: int):
    from audits.reports.page_headers import generate_page_header_report

    generate_page_header_report(run_pk, audit_pk, page_pk)


@shared_task
def page_weights(run_pk: int, audit_pk: int, page_pk: int):
    from audits.reports.page_weights import generate_page_weights_report

    generate_page_weights_report(run_pk, audit_pk, page_pk)


@shared_task
def lighthouse_audit(run_pk: int, audit_pk: int, page_pk: int):
    from audits.reports.lighthouse import generate_lighthouse_report

    generate_lighthouse_report(run_pk, audit_pk, page_pk)
