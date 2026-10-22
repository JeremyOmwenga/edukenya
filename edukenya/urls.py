from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # set_language view used by the EN/SW toggle (stores choice in a cookie)
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("", include("landing.urls")),
]
