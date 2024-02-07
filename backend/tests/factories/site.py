import factory

from metrics.models import Site


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    name = factory.Faker("name")
    slug = factory.Faker("slug")
    url = factory.Faker("domain_name")
    enabled = True
