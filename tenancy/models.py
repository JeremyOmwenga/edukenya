from django.conf import settings
from django.db import models
from django_tenants.models import DomainMixin, TenantMixin

from .validators import validate_knec_code


class Client(TenantMixin):
    """
    A school (or the platform itself for the public schema).

    A Client row is only created when the super admin APPROVES a school
    application, so a school that has not been approved has no schema and no
    domain at all. `status` adds a second gate for later suspension (e.g.
    unpaid subscription): the middleware refuses every request to a school
    that is not ACTIVE.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    name = models.CharField(max_length=200)
    knec_code = models.CharField(
        max_length=8, unique=True, null=True, blank=True, validators=[validate_knec_code]
    )
    county = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    status_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Never drop a school's data automatically. Deleting a school is a
    # deliberate, manual operation.
    auto_drop_schema = False
    auto_create_schema = True

    def __str__(self):
        return self.name

    @property
    def is_public(self):
        return self.schema_name == settings.PUBLIC_SCHEMA_NAME

    @property
    def is_accessible(self):
        return self.is_public or self.status == self.Status.ACTIVE


class Domain(DomainMixin):
    pass
