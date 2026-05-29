import factory

from lighthouse.models import Snapshot as LHSnapshot, SnapshotCategory
from sites.models import Snapshot


class SnapshotFactory(factory.django.DjangoModelFactory):
    """Creates a sites.Snapshot — the parent audit record used by the API."""

    class Meta:
        model = Snapshot

    site = factory.SubFactory("tests.factories.SiteFactory")
    platform = "mobile"
    status = Snapshot.Status.PENDING


class LHSnapshotFactory(factory.django.DjangoModelFactory):
    """Creates a lighthouse.Snapshot attached to a sites.Snapshot."""

    class Meta:
        model = LHSnapshot

    snapshot = factory.SubFactory(SnapshotFactory)
    status = LHSnapshot.Status.PENDING


class SnapshotCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SnapshotCategory

    snapshot = factory.SubFactory(LHSnapshotFactory)
    category_id = "performance"
    title = "Performance"
    poor_count = 0
    needs_count = 1
    good_count = 0
    score_avg = 75.0
