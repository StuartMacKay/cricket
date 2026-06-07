from django.core.management.base import BaseCommand

from api.models import APIKey


class Command(BaseCommand):
    help = "Create a named API key for local development"

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Development", help="Key name")

    def handle(self, *args, **options):
        name = options["name"]
        try:
            api_key = APIKey.objects.get(name=name)
            self.stdout.write(f"{api_key.key}")
        except APIKey.DoesNotExist:
            api_key = APIKey.objects.create(name=name)
            self.stdout.write(f"{api_key.key}")
