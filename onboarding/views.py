import logging

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from edukenya.security import client_ip, rate_limited

from . import emails, services
from .forms import ResendVerificationForm, SchoolRegistrationForm
from .models import SchoolApplication, new_nonce
from .tokens import read_token

logger = logging.getLogger("edukenya.onboarding")
S = SchoolApplication.Status


class EmailSendFailed(Exception):
    pass


@require_http_methods(["GET", "POST"])
def register(request):
    if request.method == "GET":
        return render(request, "onboarding/register.html", {"form": SchoolRegistrationForm()})

    ip = client_ip(request)
    if rate_limited("register_ip", ip):
        return render(request, "onboarding/rate_limited.html", status=429)

    services.expire_stale_applications()
    form = SchoolRegistrationForm(request.POST)

    if form.is_bot:
        logger.warning("registration honeypot triggered ip=%s", ip)
        return redirect("onboarding:check_email")

    if not form.is_valid():
        return render(request, "onboarding/register.html", {"form": form}, status=400)

    data = form.cleaned_data
    language = get_language() or "en"
    email = data["admin_email"]

    # Same response whether or not the email is already in use (no account enumeration).
    if SchoolApplication.objects.filter(admin_email=email, status__in=SchoolApplication.HOLDING_STATES).exists():
        make_password(data["password1"])  # keep response time similar to the real path
        try:
            emails.send_already_registered(email, language)
        except Exception:  # noqa: BLE001
            logger.exception("could not send already-registered notice")
        return redirect("onboarding:check_email")

    try:
        with transaction.atomic():
            app = SchoolApplication.objects.create(
                school_name=data["school_name"].strip(),
                knec_code=data["knec_code"],
                county=data["county"],
                subdomain=data["subdomain"],
                admin_full_name=data["admin_full_name"].strip(),
                admin_email=email,
                admin_password_hash=make_password(data["password1"]),
                language=language,
                created_ip=ip,
            )
            try:
                emails.send_verification(app)
            except Exception as exc:
                logger.exception("verification email failed; rolling back application")
                raise EmailSendFailed from exc
    except IntegrityError:
        # Lost a race with another registration for the same code/subdomain.
        form.add_error(None, _("Someone just registered with these details. Please check the KNEC code and web address."))
        return render(request, "onboarding/register.html", {"form": form}, status=400)
    except EmailSendFailed:
        form.add_error(None, _("We could not send the confirmation email right now. Please try again in a few minutes."))
        return render(request, "onboarding/register.html", {"form": form}, status=503)

    return redirect("onboarding:check_email")


def check_email(request):
    return render(request, "onboarding/check_email.html")


@require_http_methods(["GET", "POST"])
def verify(request, token):
    """
    GET only shows a confirm button. The email is verified on POST, so link
    scanners in mail clients (which follow links automatically) cannot
    verify an address on someone's behalf.
    """
    parsed = read_token(token)
    if parsed is None:
        return render(request, "onboarding/verify_invalid.html", status=400)

    if request.method == "GET":
        return render(request, "onboarding/verify_confirm.html", {"token": token})

    app = services.verify_email(*parsed)
    if app is None:
        return render(request, "onboarding/verify_invalid.html", status=400)
    return redirect("onboarding:verified")


def verified(request):
    return render(request, "onboarding/verified.html")


@require_http_methods(["GET", "POST"])
def resend(request):
    form = ResendVerificationForm(request.POST or None)
    if request.method == "POST":
        ip = client_ip(request)
        if rate_limited("resend_ip", ip):
            return render(request, "onboarding/rate_limited.html", status=429)
        if form.is_valid():
            email = form.cleaned_data["email"]
            services.expire_stale_applications()
            if not rate_limited("resend_email", email):
                app = SchoolApplication.objects.filter(admin_email=email, status=S.PENDING_EMAIL).first()
                if app is not None:
                    app.verification_nonce = new_nonce()  # old links stop working
                    app.save(update_fields=["verification_nonce", "updated_at"])
                    try:
                        emails.send_verification(app)
                    except Exception:  # noqa: BLE001
                        logger.exception("resend verification failed")
            # Same message whatever happened above.
            messages.info(request, _("If that email is waiting for confirmation, we have sent a new link."))
            return redirect("onboarding:resend")
    return render(request, "onboarding/resend.html", {"form": form})
