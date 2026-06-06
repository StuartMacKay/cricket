import factory
from audits.models import Run


class RunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Run

    job = factory.SubFactory("tests.factories.job.JobFactory")
    status = Run.Status.RUNNING
    total_tasks = 0
    completed_tasks = 0
