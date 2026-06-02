import factory

from headers.models import Job as HeadersJob, Run as HeadersRun
from lighthouse.models import Job as LighthouseJob, Run as LighthouseRun
from pageweight.models import Job as PageweightJob, Run as PageweightRun


class LighthouseJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LighthouseJob

    site               = factory.SubFactory("tests.factories.SiteFactory")
    url_source         = "url_list"
    url_value          = "https://example.com/"
    platform           = "mobile"
    cat_performance    = True
    cat_accessibility  = True
    cat_best_practices = True
    cat_seo            = True


class LighthouseRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LighthouseRun

    job    = factory.SubFactory(LighthouseJobFactory)
    status = LighthouseRun.Status.PENDING


class HeadersJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HeadersJob

    site       = factory.SubFactory("tests.factories.SiteFactory")
    url_source = "url_list"
    url_value  = "https://example.com/"


class HeadersRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HeadersRun

    job    = factory.SubFactory(HeadersJobFactory)
    status = HeadersRun.Status.PENDING


class PageweightJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageweightJob

    site       = factory.SubFactory("tests.factories.SiteFactory")
    url_source = "url_list"
    url_value  = "https://example.com/"
    device     = "mobile"


class PageweightRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PageweightRun

    job    = factory.SubFactory(PageweightJobFactory)
    status = PageweightRun.Status.PENDING
