import factory
from audits.models import Finding


class FindingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Finding

    page = factory.SubFactory("tests.factories.page.PageFactory")
    report = factory.SubFactory("tests.factories.report.ReportFactory")
    type = "dead-link"
    title = factory.Sequence(lambda n: f"Finding {n}")
    description = ""
    url = ""
    severity = Finding.Severity.WARNING
    source = ""
    data = None
