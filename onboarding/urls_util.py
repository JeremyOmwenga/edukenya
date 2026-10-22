from django.conf import settings
from django.urls import reverse


def public_url(viewname, *args):
    """Absolute URL on the root domain (used in emails)."""
    path = reverse(viewname, args=args, urlconf=settings.PUBLIC_SCHEMA_URLCONF)
    return f"{settings.SITE_SCHEME}://{settings.BASE_DOMAIN}{settings.SITE_PORT}{path}"


def school_url(subdomain, viewname, *args):
    """Absolute URL on a school's own subdomain (used in emails)."""
    path = reverse(viewname, args=args, urlconf=settings.ROOT_URLCONF)
    return f"{settings.SITE_SCHEME}://{subdomain}.{settings.BASE_DOMAIN}{settings.SITE_PORT}{path}"
