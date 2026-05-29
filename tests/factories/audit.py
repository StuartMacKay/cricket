import factory

from lighthouse.models import AuditDefinition, PageAudit, PageCategory


class AuditDefinitionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AuditDefinition
        django_get_or_create = ("audit_id",)

    audit_id = factory.Sequence(lambda n: f"audit-{n}")
    category_id = "performance"
    title = factory.Faker("sentence", nb_words=4)
    description = ""
    weight = 10.0


class PageCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageCategory

    page = factory.SubFactory("tests.factories.PageFactory")
    category_id = "performance"
    title = "Performance"
    score = 85
    rating = "needs-improvement"


class PageAuditFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageAudit

    page = factory.SubFactory("tests.factories.PageFactory")
    audit = factory.SubFactory(AuditDefinitionFactory)
    score = 85
    rating = "needs-improvement"
    value = None
    units = ""
    details = None
