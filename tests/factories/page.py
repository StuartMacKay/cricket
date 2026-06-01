import factory

from lighthouse.models import PageResult
from sites.models import Page


class PageFactory(factory.django.DjangoModelFactory):
    """Creates a sites.Page — the shared URL record within a Scan."""

    class Meta:
        model = Page

    url = factory.Faker("url")
    scan = factory.SubFactory("tests.factories.ScanFactory")


class PageResultFactory(factory.django.DjangoModelFactory):
    """Creates a lighthouse.PageResult for a sites.Page."""

    class Meta:
        model = PageResult

    page = factory.SubFactory(PageFactory)
    audited = False
