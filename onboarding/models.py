import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q

from tenancy.counties import COUNTY_CHOICES
from tenancy.validators import validate_knec_code, validate_subdomain


def new_nonce():
    return secrets.token_urlsafe(16)


class SchoolApplication(models.Model):
    """
    A request to join EduKenya, stored in the public schema.

    Lifecycle:
      pending_email  -> admin must click the emailed link
      pending_review -> email verified; waiting for the platform super admin
      approved       -> school schema + subdomain created, admin account created
      rejected       -> super admin gave a reason, admin was emailed
      expired        -> email never verified in time

    No school schema, domain or user account exists until `approved`.
    """

    class Status(models.TextChoices):
        PENDING_EMAIL = "pending_email", "Waiting for email verification"
        PENDING_REVIEW = "pending_review", "Waiting for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    # States that "hold" a KNEC code, subdomain and email so nobody else can take them.
    HOLDING_STATES = (Status.PENDING_EMAIL, Status.PENDING_REVIEW, Status.APPROVED)

    school_name = models.CharField(max_length=200)
    knec_code = models.CharField(max_length=8, validators=[validate_knec_code])
    county = models.CharField(max_length=40, choices=COUNTY_CHOICES)
    subdomain = models.CharField(max_length=30, validators=[validate_subdomain])

    admin_full_name = models.CharField(max_length=150)
    admin_email = models.EmailField()
    # Argon2 hash of the admin's chosen password. Copied into the school's own
    # users table on approval, then wiped from here.
    admin_password_hash = models.CharField(max_length=256, blank=True)
    language = models.CharField(max_length=8, default="en")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_EMAIL)
    # Rotated every time a link is issued or used, so old links stop working.
    verification_nonce = models.CharField(max_length=32, default=new_nonce)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    client = models.OneToOneField(
        "tenancy.Client", null=True, blank=True, on_delete=models.SET_NULL, related_name="application"
    )

    created_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["knec_code"], condition=Q(status__in=["pending_email", "pending_review", "approved"]),
                name="uniq_active_application_knec",
            ),
            models.UniqueConstraint(
                fields=["subdomain"], condition=Q(status__in=["pending_email", "pending_review", "approved"]),
                name="uniq_active_application_subdomain",
            ),
            models.UniqueConstraint(
                fields=["admin_email"], condition=Q(status__in=["pending_email", "pending_review", "approved"]),
                name="uniq_active_application_email",
            ),
        ]

    def __str__(self):
        return f"{self.school_name} ({self.knec_code})"

    @property
    def full_domain(self):
        return f"{self.subdomain}.{settings.BASE_DOMAIN}"
