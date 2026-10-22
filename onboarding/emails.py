"""
All onboarding emails. Each is rendered in the applicant's chosen language.
Sending errors are NOT swallowed: callers decide how to react.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.translation import gettext as _

from .tokens import make_token
from .urls_util import public_url, school_url


def _send(to, subject, template, context, language):
    with translation.override(language):
        body = render_to_string(f"onboarding/email/{template}.txt", context)
        send_mail(str(subject()), body, settings.DEFAULT_FROM_EMAIL, [to], fail_silently=False)


def send_verification(app):
    link = public_url("onboarding:verify", make_token(app))
    _send(app.admin_email, lambda: _("Confirm your email for EduKenya"), "verify",
          {"app": app, "link": link, "hours": settings.APPLICATION_VERIFY_MAX_AGE // 3600}, app.language)


def send_already_registered(email, language):
    """Sent instead of a second application, so the form never reveals which emails exist."""
    _send(email, lambda: _("Someone tried to register a school with your email"), "already_registered",
          {"resend_link": public_url("onboarding:resend")}, language)


def send_approved(app):
    link = school_url(app.subdomain, "school:login")
    _send(app.admin_email, lambda: _("Your school is approved on EduKenya"), "approved",
          {"app": app, "link": link}, app.language)


def send_rejected(app):
    _send(app.admin_email, lambda: _("Update on your EduKenya school application"), "rejected",
          {"app": app}, app.language)


def notify_platform_admin(app):
    if not settings.PLATFORM_NOTIFY_EMAIL:
        return
    link = public_url("console:application_detail", app.pk)
    body = (
        f"{app.school_name} (KNEC {app.knec_code}, {app.county}) verified their email "
        f"and is waiting for approval.\n\nReview it here: {link}\n"
    )
    send_mail(f"[EduKenya] New school waiting: {app.school_name}", body,
              settings.DEFAULT_FROM_EMAIL, [settings.PLATFORM_NOTIFY_EMAIL], fail_silently=False)
