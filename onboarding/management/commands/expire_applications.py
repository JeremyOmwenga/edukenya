from django.core.management.base import BaseCommand

from onboarding.services import expire_stale_applications


class Command(BaseCommand):
    help = "Mark unverified school applications older than the link lifetime as expired (run daily)."

    def handle(self, *args, **options):
        n = expire_stale_applications()
        self.stdout.write(f"Expired {n} application(s).")
