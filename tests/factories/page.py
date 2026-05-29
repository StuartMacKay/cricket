import factory

from lighthouse.models import Page


class PageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Page

    url = factory.Faker("url")
    audited = False
    snapshot = factory.SubFactory("tests.factories.LighthouseSnapshotFactory")
