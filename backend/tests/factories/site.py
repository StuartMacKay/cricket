import factory

from metrics.models import Site


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    name = factory.Faker("domain_name")
    url = factory.Faker("domain_name")
    sitemap_file = factory.django.FileField(data=b"")
    config_file = factory.django.FileField(data=b"")
    enabled = True
