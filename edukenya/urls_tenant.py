"""URLs served on a school's own subdomain. Nothing from the public site is reachable here."""
from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("", include("school.urls")),
]
