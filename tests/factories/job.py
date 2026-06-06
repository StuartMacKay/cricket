import factory
from audits.models import Job


class JobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Job
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Job {n}")
    site = factory.SubFactory("tests.factories.site.SiteFactory")
    urls = "https://example.com/"
    device = Job.Device.MOBILE
    enabled = True

    @factory.post_generation
    def audits(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for audit in extracted:
                self.audits.add(audit)
