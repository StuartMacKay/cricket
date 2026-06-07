from django.core.management.base import BaseCommand

from audits.models import Audit, Job, Site

DEMO_URL = "https://www.example.com/"


class Command(BaseCommand):
    help = "Create a demo site and job for local development"

    def handle(self, *args, **options):
        site, created = Site.objects.get_or_create(
            slug="example",
            defaults={"name": "Example", "url": DEMO_URL},
        )
        if created:
            self.stdout.write(f"Created site: {site.name} ({site.url})")
        else:
            self.stdout.write(f"Site already exists: {site.name}")

        job, created = Job.objects.get_or_create(
            name="Example Home Page",
            site=site,
            defaults={
                "urls": DEMO_URL,
                "device": "desktop",
                "enabled": True,
            },
        )
        if created:
            audits = Audit.objects.all()
            job.audits.set(audits)
            self.stdout.write(
                f"Created job: {job.name} with {audits.count()} audits"
            )
        else:
            self.stdout.write(f"Job already exists: {job.name}")
