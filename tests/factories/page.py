import factory

from metrics.models import Page


class PageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Page

    url = factory.Faker("url")
    name = factory.Faker("name")
    enabled = True
    snapshot = factory.SubFactory("tests.factories.SnapshotFactory")
