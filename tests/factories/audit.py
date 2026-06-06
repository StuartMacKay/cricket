import factory

from audits.models import Audit


class AuditFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Audit

    name = factory.Sequence(lambda n: f"Audit {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
    task = "audits.tasks.page_headers"
    description = ""
