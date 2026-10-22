from django.conf import settings


def site(request):
    return {"base_domain": settings.BASE_DOMAIN}
