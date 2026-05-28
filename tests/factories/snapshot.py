import factory

from metrics.models import Snapshot


class SnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Snapshot

    site = factory.SubFactory("tests.factories.SiteFactory")
