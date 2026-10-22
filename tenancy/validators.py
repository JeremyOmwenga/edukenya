import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

KNEC_CODE_RE = re.compile(r"^\d{8}$")
# 3 to 30 chars, lowercase letters/digits/hyphens, no leading/trailing hyphen.
SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,28})[a-z0-9]$")


def validate_knec_code(value):
    if not KNEC_CODE_RE.fullmatch(value or ""):
        raise ValidationError(_("The KNEC school code must be exactly 8 digits."), code="knec_format")


def validate_subdomain(value):
    value = value or ""
    if not SUBDOMAIN_RE.fullmatch(value):
        raise ValidationError(
            _("Use 3 to 30 lowercase letters, numbers or hyphens. It cannot start or end with a hyphen."),
            code="subdomain_format",
        )
    # "--" is how punycode (xn--) look-alike domains start; block it entirely.
    if "--" in value:
        raise ValidationError(_("The web address cannot contain two hyphens in a row."), code="subdomain_hyphens")
    if value in settings.RESERVED_SUBDOMAINS:
        raise ValidationError(_("This web address is reserved. Please choose another."), code="subdomain_reserved")


def schema_name_for(subdomain):
    """Postgres schema name for a school. Prefixed so it can never collide with 'public' or pg_*."""
    return "school_" + subdomain.replace("-", "_")
