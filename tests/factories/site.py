import factory
from audits.models import Site


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    name = factory.Sequence(lambda n: f"Site {n}")
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-"))
    url = factory.Sequence(lambda n: f"https://site-{n}.example.com/")
    environment = Site.Environment.PRODUCTION
