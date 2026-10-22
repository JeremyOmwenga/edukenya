"""
Business logic for school applications. Views stay thin; everything that
changes state goes through here so it is locked, audited and testable.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from django_tenants.utils import schema_context

from accounts.models import User
from console.audit import record
from tenancy.models import Client, Domain
from tenancy.validators import schema_name_for

from . import emails
from .models import SchoolApplication, new_nonce

logger = logging.getLogger("edukenya.onboarding")
S = SchoolApplication.Status


class ApplicationStateError(Exception):
    """The application is not in a state that allows this action."""


def expire_stale_applications():
    """Release KNEC codes / subdomains held by applications whose email was never verified."""
    cutoff = timezone.now() - timedelta(seconds=settings.APPLICATION_VERIFY_MAX_AGE)
    return SchoolApplication.objects.filter(status=S.PENDING_EMAIL, created_at__lt=cutoff).update(
        status=S.EXPIRED, admin_password_hash="", updated_at=timezone.now()
    )


def subdomain_taken(subdomain):
    return (
        Domain.objects.filter(domain=f"{subdomain}.{settings.BASE_DOMAIN}").exists()
        or SchoolApplication.objects.filter(subdomain=subdomain, status__in=SchoolApplication.HOLDING_STATES).exists()
    )


def knec_taken(knec_code):
    return (
        Client.objects.filter(knec_code=knec_code).exists()
        or SchoolApplication.objects.filter(knec_code=knec_code, status__in=SchoolApplication.HOLDING_STATES).exists()
    )


@transaction.atomic
def verify_email(app_id, nonce):
    """
    Marks the application's email as verified. Returns the application, or
    None if the link is stale/used. The nonce is rotated so the link is single use.
    """
    app = SchoolApplication.objects.select_for_update().filter(pk=app_id).first()
    if app is None or app.status != S.PENDING_EMAIL or app.verification_nonce != nonce:
        return None
    app.status = S.PENDING_REVIEW
    app.email_verified_at = timezone.now()
    app.verification_nonce = new_nonce()
    app.save(update_fields=["status", "email_verified_at", "verification_nonce", "updated_at"])
    transaction.on_commit(lambda: _safe(emails.notify_platform_admin, app))
    return app


def approve(app_id, actor, ip=None):
    """
    Creates the school's schema, its subdomain and its first admin account.

    Runs in ONE transaction: PostgreSQL DDL is transactional, so if any step
    fails the schema, domain and user are all rolled back together.
    """
    with transaction.atomic():
        app = SchoolApplication.objects.select_for_update().get(pk=app_id)
        if app.status != S.PENDING_REVIEW:
            raise ApplicationStateError(f"Cannot approve an application in state '{app.status}'.")
        if not app.admin_password_hash:
            raise ApplicationStateError("Application has no admin credentials.")
        if Client.objects.filter(knec_code=app.knec_code).exists():
            raise ApplicationStateError("A school with this KNEC code already exists.")
        if Domain.objects.filter(domain=app.full_domain).exists():
            raise ApplicationStateError("That subdomain is already in use.")

        client = Client(
            schema_name=schema_name_for(app.subdomain),
            name=app.school_name,
            knec_code=app.knec_code,
            county=app.county,
            status=Client.Status.ACTIVE,
        )
        client.save(verbosity=0)  # creates + migrates the schema
        connection.set_schema_to_public()
        Domain.objects.create(domain=app.full_domain, tenant=client, is_primary=True)

        with schema_context(client.schema_name):
            admin = User(
                email=app.admin_email,
                full_name=app.admin_full_name,
                role=User.Role.SCHOOL_ADMIN,
                email_verified_at=app.email_verified_at,
            )
            admin.password = app.admin_password_hash  # already an Argon2 hash
            admin.save()

        app.status = S.APPROVED
        app.client = client
        app.reviewed_by = actor
        app.reviewed_at = timezone.now()
        app.admin_password_hash = ""
        app.save()

        record(actor, "application.approved", app, ip=ip,
               details={"schema": client.schema_name, "domain": app.full_domain})
        transaction.on_commit(lambda: _safe(emails.send_approved, app))
    return app


@transaction.atomic
def reject(app_id, actor, reason, ip=None):
    reason = (reason or "").strip()
    if len(reason) < 10:
        raise ApplicationStateError("Please give a reason of at least 10 characters.")
    app = SchoolApplication.objects.select_for_update().get(pk=app_id)
    if app.status not in (S.PENDING_REVIEW, S.PENDING_EMAIL):
        raise ApplicationStateError(f"Cannot reject an application in state '{app.status}'.")
    app.status = S.REJECTED
    app.rejection_reason = reason
    app.reviewed_by = actor
    app.reviewed_at = timezone.now()
    app.admin_password_hash = ""
    app.save()
    record(actor, "application.rejected", app, ip=ip, details={"reason": reason})
    transaction.on_commit(lambda: _safe(emails.send_rejected, app))
    return app


@transaction.atomic
def set_school_status(client_id, actor, new_status, reason, ip=None):
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ApplicationStateError("Please give a reason.")
    client = Client.objects.select_for_update().get(pk=client_id)
    if client.is_public:
        raise ApplicationStateError("The platform itself cannot be suspended.")
    if new_status not in Client.Status.values:
        raise ApplicationStateError("Unknown status.")
    old = client.status
    client.status = new_status
    client.status_reason = reason
    client.save(update_fields=["status", "status_reason"])
    record(actor, f"school.{new_status}", client, ip=ip, details={"from": old, "reason": reason})
    return client


def _safe(fn, *args):
    """Post-commit emails: the state change already happened, so log failures loudly instead of crashing."""
    try:
        fn(*args)
    except Exception:  # noqa: BLE001
        logger.exception("email failed: %s", getattr(fn, "__name__", fn))
