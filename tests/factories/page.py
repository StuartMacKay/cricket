import factory
from audits.models import Page


class PageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Page

    site = factory.SubFactory("tests.factories.site.SiteFactory")
    url = factory.Sequence(lambda n: f"https://example-{n}.com/page/")
