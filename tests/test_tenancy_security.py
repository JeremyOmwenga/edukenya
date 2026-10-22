import os
import subprocess
import sys
from pathlib import Path

from django.core import mail
from django.db import connection
from django_tenants.utils import schema_context, schema_exists

from accounts.models import User
from console.models import AuditEvent
from onboarding import services
from onboarding.models import SchoolApplication
from tenancy.models import Client, Domain

from .base import PASSWORD, PlatformTestCase

S = SchoolApplication.Status
ROOT_DIR = Path(__file__).resolve().parent.parent


class HostHandlingTests(PlatformTestCase):
    def test_landing_on_root_domain(self):
        self.assertEqual(self.get("/").status_code, 200)

    def test_foreign_host_rejected(self):
        # Not in ALLOWED_HOSTS: django-tenants answers a bare 404 before any view runs.
        for host in ("evil.example.com", "localhost.evil.com", "greenhill.localhost.evil.com"):
            with self.subTest(host=host):
                r = self.get("/", host=host)
                self.assertEqual(r.status_code, 404)
                self.assertNotIn(b"EduKenya", r.content)

    def test_unknown_subdomain_404(self):
        self.assertEqual(self.get("/", host="nope.localhost").status_code, 404)
        self.assertEqual(self.get("/login/", host="nope.localhost").status_code, 404)

    def test_pending_school_has_no_site(self):
        self.make_pending_review(subdomain="greenhill")
        self.assertEqual(self.get("/login/", host="greenhill.localhost").status_code, 404)

    def test_security_headers(self):
        r = self.get("/")
        self.assertIn("default-src 'self'", r["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")


class ApprovalTests(PlatformTestCase):
    def test_approve_creates_isolated_school_and_admin(self):
        app = self.make_pending_review()
        self.approve(app)
        app.refresh_from_db()

        self.assertEqual(app.status, S.APPROVED)
        self.assertEqual(app.admin_password_hash, "")  # wiped from public schema
        self.assertTrue(schema_exists("school_greenhill"))
        self.assertTrue(Domain.objects.filter(domain="greenhill.localhost").exists())
        # Admin lives only in the school's schema, not in public.
        self.assertFalse(User.objects.filter(email=app.admin_email).exists())
        with schema_context("school_greenhill"):
            admin = User.objects.get(email=app.admin_email)
            self.assertEqual(admin.role, User.Role.SCHOOL_ADMIN)
            self.assertFalse(admin.is_superuser)
        self.assertTrue(AuditEvent.objects.filter(action="application.approved").exists())
        self.assertIn("greenhill.localhost", mail.outbox[-1].body)

        r = self.post("/login/", {"username": app.admin_email, "password": PASSWORD}, host="greenhill.localhost")
        self.assertRedirects(r, "/dashboard/", fetch_redirect_response=False)
        self.assertContains(self.get("/dashboard/", host="greenhill.localhost"), "Amina Otieno")

    def test_cannot_approve_twice_or_unverified(self):
        app = self.make_pending_review()
        self.approve(app)
        with self.assertRaises(services.ApplicationStateError):
            self.approve(app)
        unverified = self.make_pending_review(subdomain="other", knec="22222222", email="o@example.com")
        unverified.status = S.PENDING_EMAIL
        unverified.save()
        with self.assertRaises(services.ApplicationStateError):
            self.approve(unverified)
        self.assertFalse(schema_exists("school_other"))

    def test_reject_requires_reason_and_emails_it(self):
        app = self.make_pending_review()
        boss = self.make_superuser()
        with self.assertRaises(services.ApplicationStateError):
            services.reject(app.pk, boss, "too short")
        with self.captureOnCommitCallbacks(execute=True):
            services.reject(app.pk, boss, "KNEC code does not match our records.")
        app.refresh_from_db()
        self.assertEqual(app.status, S.REJECTED)
        self.assertEqual(app.admin_password_hash, "")
        self.assertIn("KNEC code does not match our records.", mail.outbox[-1].body)
        self.assertFalse(schema_exists("school_greenhill"))


class IsolationTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.a = self.make_pending_review(subdomain="alpha", knec="11111111", email="head@alpha.ac.ke")
        self.b = self.make_pending_review(subdomain="bravo", knec="22222222", email="head@bravo.ac.ke")
        self.a = self.approve(self.a)
        self.b = self.approve(self.b)

    def test_session_from_one_school_is_useless_on_another(self):
        self.post("/login/", {"username": "head@alpha.ac.ke", "password": PASSWORD}, host="alpha.localhost")
        self.assertEqual(self.get("/dashboard/", host="alpha.localhost").status_code, 200)
        # The test client replays ALL cookies to every host: exactly what an
        # attacker copying a session cookie would do.
        r = self.get("/dashboard/", host="bravo.localhost")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login/", r["Location"])

    def test_credentials_from_one_school_do_not_work_on_another(self):
        r = self.post("/login/", {"username": "head@alpha.ac.ke", "password": PASSWORD}, host="bravo.localhost")
        self.assertEqual(r.status_code, 200)  # form re-rendered with error
        self.assertContains(r, "Incorrect email or password")

    def test_suspended_school_is_completely_blocked(self):
        boss = self.make_superuser()
        self.post("/login/", {"username": "head@alpha.ac.ke", "password": PASSWORD}, host="alpha.localhost")
        services.set_school_status(self.a.client_id, boss, Client.Status.SUSPENDED, "Unpaid subscription")
        for path in ("/", "/login/", "/dashboard/"):
            self.assertEqual(self.get(path, host="alpha.localhost").status_code, 404)
        services.set_school_status(self.a.client_id, boss, Client.Status.ACTIVE, "Payment received")
        self.assertEqual(self.get("/dashboard/", host="alpha.localhost").status_code, 200)
        # Bravo is unaffected (and ignores alpha's session).
        self.assertEqual(self.get("/login/", host="bravo.localhost").status_code, 200)

    def test_school_login_is_rate_limited(self):
        for _ in range(5):
            self.post("/login/", {"username": "head@alpha.ac.ke", "password": "wrong"}, host="alpha.localhost")
        r = self.post("/login/", {"username": "head@alpha.ac.ke", "password": PASSWORD}, host="alpha.localhost")
        self.assertEqual(r.status_code, 429)


class ConsoleAccessTests(PlatformTestCase):
    def test_anonymous_redirected_to_console_login(self):
        r = self.get("/console/")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/console/login/"))

    def test_console_not_on_school_domains(self):
        app = self.make_pending_review()
        self.approve(app)
        self.assertEqual(self.get("/console/", host="greenhill.localhost").status_code, 404)
        self.assertEqual(self.get("/console/login/", host="greenhill.localhost").status_code, 404)

    def test_non_superuser_cannot_sign_in_or_view(self):
        User.objects.create_user(email="staff@example.com", password=PASSWORD, role=User.Role.SCHOOL_ADMIN)
        r = self.post("/console/login/", {"username": "staff@example.com", "password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Incorrect email or password")
        self.assertTrue(AuditEvent.objects.filter(action="console.login_failed").exists())

    def test_superuser_can_approve_via_console_and_get_requests_cannot_change_state(self):
        app = self.make_pending_review()
        self.make_superuser()
        self.post("/console/login/", {"username": "boss@example.com", "password": PASSWORD})
        self.assertEqual(self.get(f"/console/applications/{app.pk}/").status_code, 200)
        self.assertEqual(self.get(f"/console/applications/{app.pk}/approve/").status_code, 405)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.post(f"/console/applications/{app.pk}/approve/")
        self.assertEqual(r.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, S.APPROVED)

    def test_reject_via_console_requires_reason(self):
        app = self.make_pending_review()
        self.make_superuser()
        self.post("/console/login/", {"username": "boss@example.com", "password": PASSWORD})
        self.assertEqual(self.post(f"/console/applications/{app.pk}/reject/", {"reason": ""}).status_code, 400)
        app.refresh_from_db()
        self.assertEqual(app.status, S.PENDING_REVIEW)

    def test_console_login_rate_limited(self):
        for _ in range(5):
            self.post("/console/login/", {"username": "boss@example.com", "password": "nope"})
        self.assertEqual(self.post("/console/login/", {"username": "boss@example.com", "password": "x"}).status_code, 429)

    def test_audit_events_are_append_only(self):
        self.make_superuser()
        self.post("/console/login/", {"username": "boss@example.com", "password": PASSWORD})
        event = AuditEvent.objects.first()
        with self.assertRaises(RuntimeError):
            event.save()
        with self.assertRaises(RuntimeError):
            event.delete()


class ProductionGuardrailTests(PlatformTestCase):
    def test_refuses_to_boot_with_unsafe_production_settings(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "EDUKENYA_"))}
        env.update({"DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": "", "DJANGO_SETTINGS_MODULE": "edukenya.settings"})
        proc = subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            cwd=ROOT_DIR, env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("Unsafe production settings", proc.stderr)
        self.assertIn("DJANGO_SECRET_KEY", proc.stderr)
        self.assertIn("EDUKENYA_BASE_DOMAIN", proc.stderr)
        connection.set_schema_to_public()
