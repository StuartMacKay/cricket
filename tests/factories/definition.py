import factory
from audits.models import Definition


class DefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Definition

    name = factory.Sequence(lambda n: f"Definition {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
    description = ""
    weight = None
    audit = factory.SubFactory("tests.factories.audit.AuditFactory")
