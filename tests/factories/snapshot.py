import factory

from metrics.models import Snapshot


class SnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Snapshot

    name = factory.Faker("name")
    url = factory.Faker("url")
    enabled = True
    site = factory.SubFactory("tests.factories.SiteFactory")
