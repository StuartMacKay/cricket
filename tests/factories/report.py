import factory
from audits.models import Report


class ReportFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Report

    page = factory.SubFactory("test.factories.page.PageFactory")
    audit = factory.SubFactory("tests.factories.audit.AuditFactory")
    run = factory.SubFactory("tests.factories.run.RunFactory")
    data = factory.LazyFunction(dict)
    error = ""
