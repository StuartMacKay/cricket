import factory

from sites.models import Site


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    name        = factory.Faker("domain_name")
    primary_url = factory.Faker("url")
