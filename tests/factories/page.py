import factory

from lighthouse.models import Page as LighthousePage


class LighthousePageFactory(factory.django.DjangoModelFactory):
    """Creates a lighthouse.Page (one URL within a Lighthouse Run)."""

    class Meta:
        model = LighthousePage

    run     = factory.SubFactory("tests.factories.LighthouseRunFactory")
    url     = factory.Faker("url")
    audited = False


# Keep a generic alias for backwards compatibility in tests
PageFactory = LighthousePageFactory
