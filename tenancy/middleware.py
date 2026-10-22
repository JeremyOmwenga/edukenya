import logging

from django.http import Http404
from django_tenants.middleware.main import TenantMainMiddleware

logger = logging.getLogger("edukenya.security")


class TenantAccessMiddleware(TenantMainMiddleware):
    """
    Resolves the school from the Host header (django-tenants), then refuses
    to serve any school that is not ACTIVE.

    Blocked and unknown schools both get the same plain 404, so nobody can
    probe subdomains to learn which schools exist or are suspended.
    """

    def process_request(self, request):
        response = super().process_request(request)
        if response is not None:
            return response
        tenant = request.tenant
        if not tenant.is_accessible:
            logger.info("blocked request to inactive school schema=%s", tenant.schema_name)
            raise Http404("Not found")
        return None
