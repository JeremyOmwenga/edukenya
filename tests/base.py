from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from onboarding.models import SchoolApplication
from tenancy.models import Client, Domain

ROOT = "localhost"
PASSWORD = "Correct-Horse-Battery-9"


class PlatformTestCase(TestCase):
    """Creates the public tenant and gives host-aware request helpers."""

    def setUp(self):
        cache.clear()
        connection.set_schema_to_public()
        self.public = Client.objects.create(schema_name="public", name="EduKenya platform")
        Domain.objects.create(domain=ROOT, tenant=self.public, is_primary=True)

    def tearDown(self):
        connection.set_schema_to_public()

    # Every request switches the DB connection to the requested school's
    # schema; switch back so test assertions always query the public schema.
    def get(self, path, host=ROOT, **kw):
        try:
            return self.client.get(path, HTTP_HOST=host, **kw)
        finally:
            connection.set_schema_to_public()

    def post(self, path, data=None, host=ROOT, **kw):
        try:
            return self.client.post(path, data or {}, HTTP_HOST=host, **kw)
        finally:
            connection.set_schema_to_public()

    def make_superuser(self, email="boss@example.com"):
        return User.objects.create_superuser(email=email, password=PASSWORD)

    def make_pending_review(self, subdomain="greenhill", knec="12345678", email="head@greenhill.ac.ke"):
        return SchoolApplication.objects.create(
            school_name=f"{subdomain.title()} Junior School",
            knec_code=knec,
            county="Nairobi",
            subdomain=subdomain,
            admin_full_name="Amina Otieno",
            admin_email=email,
            admin_password_hash=make_password(PASSWORD),
            status=SchoolApplication.Status.PENDING_REVIEW,
            email_verified_at=timezone.now(),
        )

    def approve(self, app, actor=None):
        from onboarding import services

        if actor is None:
            actor = User.objects.filter(email="approver@example.com").first() or \
                self.make_superuser(email="approver@example.com")
        with self.captureOnCommitCallbacks(execute=True):
            result = services.approve(app.pk, actor)
        connection.set_schema_to_public()
        return result
