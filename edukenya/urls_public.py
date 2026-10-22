"""URLs served on the root domain (public schema)."""
from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("register/", include("onboarding.urls")),
    path("console/", include("console.urls")),
    path("", include("landing.urls")),
]
