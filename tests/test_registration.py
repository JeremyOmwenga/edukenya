import re

from django.core import mail
from django.core.cache import cache
from django.test import override_settings

from onboarding.models import SchoolApplication
from onboarding.tokens import make_token

from .base import PASSWORD, PlatformTestCase

S = SchoolApplication.Status


def valid_data(**over):
    data = {
        "school_name": "Greenhill Junior School",
        "knec_code": "12345678",
        "county": "Nairobi",
        "subdomain": "greenhill",
        "admin_full_name": "Amina Otieno",
        "admin_email": "Head@Greenhill.ac.ke",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "website": "",
    }
    data.update(over)
    return data


class RegistrationTests(PlatformTestCase):
    def test_register_creates_pending_application_and_sends_link(self):
        r = self.post("/register/", valid_data())
        self.assertRedirects(r, "/register/check-email/", fetch_redirect_response=False)
        app = SchoolApplication.objects.get()
        self.assertEqual(app.status, S.PENDING_EMAIL)
        self.assertEqual(app.admin_email, "head@greenhill.ac.ke")
        self.assertTrue(app.admin_password_hash.startswith("argon2"))
        self.assertNotIn(PASSWORD, app.admin_password_hash)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/register/verify/", mail.outbox[0].body)

    def test_kiswahili_applicant_gets_kiswahili_page_and_email(self):
        self.client.cookies["django_language"] = "sw"
        self.assertContains(self.get("/register/"), "Sajili shule yako")
        self.post("/register/", valid_data())
        self.assertEqual(SchoolApplication.objects.get().language, "sw")
        self.assertIn("Habari Amina Otieno", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].subject, "Thibitisha barua pepe yako kwa EduKenya")

    def test_invalid_knec_and_reserved_or_lookalike_subdomains_rejected(self):
        for over in (
            {"knec_code": "1234567"},
            {"knec_code": "1234567a"},
            {"subdomain": "www"},
            {"subdomain": "mail"},
            {"subdomain": "xn--grnhill"},
            {"subdomain": "-greenhill"},
            {"subdomain": "green.hill"},
            {"subdomain": "ab"},
        ):
            with self.subTest(**over):
                cache.clear()  # this test is about validation, not the rate limiter
                r = self.post("/register/", valid_data(**over))
                self.assertEqual(r.status_code, 400)
        self.assertFalse(SchoolApplication.objects.exists())

    def test_password_mismatch_and_weak_password_rejected(self):
        self.assertEqual(self.post("/register/", valid_data(password2="different-123456")).status_code, 400)
        self.assertEqual(self.post("/register/", valid_data(password1="password", password2="password")).status_code, 400)
        self.assertFalse(SchoolApplication.objects.exists())

    def test_duplicate_knec_or_subdomain_blocked(self):
        self.make_pending_review(subdomain="greenhill", knec="12345678", email="x@example.com")
        self.assertEqual(self.post("/register/", valid_data(subdomain="other")).status_code, 400)
        self.assertEqual(self.post("/register/", valid_data(knec_code="87654321")).status_code, 400)

    def test_duplicate_email_gives_same_response_without_new_application(self):
        self.make_pending_review(subdomain="first", knec="11111111", email="head@greenhill.ac.ke")
        r = self.post("/register/", valid_data())
        self.assertRedirects(r, "/register/check-email/", fetch_redirect_response=False)
        self.assertEqual(SchoolApplication.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("already linked", mail.outbox[0].body)

    def test_honeypot_silently_drops_bots(self):
        r = self.post("/register/", valid_data(website="http://spam.example"))
        self.assertRedirects(r, "/register/check-email/", fetch_redirect_response=False)
        self.assertFalse(SchoolApplication.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_registration_is_rate_limited(self):
        for i in range(5):
            self.post("/register/", valid_data(knec_code="1", subdomain=f"s{i}xx"))
        self.assertEqual(self.post("/register/", valid_data()).status_code, 429)

    def test_register_not_reachable_on_school_subdomain(self):
        app = self.make_pending_review()
        self.approve(app)
        self.assertEqual(self.get("/register/", host="greenhill.localhost").status_code, 404)


class PageRenderTests(PlatformTestCase):
    def test_public_pages_render_in_both_languages(self):
        pages = ["/", "/register/", "/register/check-email/", "/register/verified/", "/register/resend/",
                 "/register/verify/not-a-real-token/"]
        for lang in ("en", "sw"):
            self.client.cookies["django_language"] = lang
            for path in pages:
                with self.subTest(lang=lang, path=path):
                    r = self.get(path)
                    self.assertIn(r.status_code, (200, 400))
                    self.assertContains(r, f'lang="{lang}"', status_code=r.status_code)
                    self.assertNotIn("\u2014", r.content.decode())  # no em dashes


class VerificationTests(PlatformTestCase):
    def _register(self):
        self.post("/register/", valid_data())
        link = re.search(r"https?://\S+", mail.outbox[-1].body).group(0)
        return SchoolApplication.objects.get(), link.split("localhost:8000", 1)[-1]

    def test_get_does_not_verify_post_does(self):
        app, path = self._register()
        self.assertEqual(self.get(path).status_code, 200)
        app.refresh_from_db()
        self.assertEqual(app.status, S.PENDING_EMAIL)
        r = self.post(path)
        self.assertRedirects(r, "/register/verified/", fetch_redirect_response=False)
        app.refresh_from_db()
        self.assertEqual(app.status, S.PENDING_REVIEW)
        self.assertIsNotNone(app.email_verified_at)

    def test_link_is_single_use(self):
        _, path = self._register()
        self.post(path)
        self.assertEqual(self.post(path).status_code, 400)

    def test_tampered_token_rejected(self):
        _, path = self._register()
        tampered = path[:-3] + ("A" if path[-3] != "A" else "B") + path[-2:]
        self.assertEqual(self.post(tampered).status_code, 400)
        self.assertEqual(SchoolApplication.objects.get().status, S.PENDING_EMAIL)

    def test_expired_token_rejected(self):
        app, path = self._register()
        with override_settings(APPLICATION_VERIFY_MAX_AGE=-1):
            self.assertEqual(self.post(path).status_code, 400)

    def test_resend_rotates_link(self):
        app, old_path = self._register()
        self.post("/register/resend/", {"email": "head@greenhill.ac.ke"})
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.post(old_path).status_code, 400)
        app.refresh_from_db()
        new_path = f"/register/verify/{make_token(app)}/"
        self.post(new_path)
        app.refresh_from_db()
        self.assertEqual(app.status, S.PENDING_REVIEW)

    def test_resend_for_unknown_email_looks_identical(self):
        r = self.post("/register/resend/", {"email": "nobody@example.com"}, follow=True)
        self.assertContains(r, "If that email is waiting for confirmation")
        self.assertEqual(len(mail.outbox), 0)
