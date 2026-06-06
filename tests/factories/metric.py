import factory
from audits.models import Metric


class MetricFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Metric

    report     = factory.SubFactory("tests.factories.report.ReportFactory")
    definition = factory.SubFactory("tests.factories.definition.DefinitionFactory")
    page       = factory.LazyAttribute(lambda o: o.report.page)
    measured   = factory.LazyAttribute(lambda o: o.report.run.created)
    score      = None
    rating     = None
    value      = None
    units      = ""
