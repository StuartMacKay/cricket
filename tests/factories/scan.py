import factory

from lighthouse.models import Run as LighthouseRun
from sites.models import Scan


class ScanFactory(factory.django.DjangoModelFactory):
    """Creates a sites.Scan — the parent audit record used by the API."""

    class Meta:
        model = Scan

    site = factory.SubFactory("tests.factories.SiteFactory")
    platform = "mobile"
    status = Scan.Status.PENDING


class LighthouseRunFactory(factory.django.DjangoModelFactory):
    """Creates a lighthouse.Run attached to a sites.Scan."""

    class Meta:
        model = LighthouseRun

    scan = factory.SubFactory(ScanFactory)
    status = LighthouseRun.Status.PENDING
