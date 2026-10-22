from django.conf import settings
from django.core.management.base import BaseCommand

from tenancy.models import Client, Domain


class Command(BaseCommand):
    help = "Create the public tenant and map the root domain to it. Safe to run repeatedly."

    def handle(self, *args, **options):
        client, created = Client.objects.get_or_create(
            schema_name=settings.PUBLIC_SCHEMA_NAME, defaults={"name": "EduKenya platform"}
        )
        domain, d_created = Domain.objects.get_or_create(
            domain=settings.BASE_DOMAIN, defaults={"tenant": client, "is_primary": True}
        )
        if domain.tenant_id != client.pk:
            raise SystemExit(f"{settings.BASE_DOMAIN} is mapped to another tenant. Refusing to continue.")
        self.stdout.write(
            f"public tenant {'created' if created else 'exists'}; "
            f"{settings.BASE_DOMAIN} {'mapped' if d_created else 'already mapped'}"
        )
