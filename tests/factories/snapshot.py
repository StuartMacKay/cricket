import factory

from lighthouse.models import Snapshot, SnapshotCategory


class SnapshotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Snapshot

    site = factory.SubFactory("tests.factories.SiteFactory")
    status = Snapshot.Status.PENDING
    platform = "mobile"


class SnapshotCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SnapshotCategory

    snapshot = factory.SubFactory(SnapshotFactory)
    category_id = "performance"
    title = "Performance"
    poor_count = 0
    needs_count = 1
    good_count = 0
    score_avg = 75.0
