from django.urls import path

from . import views

app_name = "onboarding"

urlpatterns = [
    path("", views.register, name="register"),
    path("check-email/", views.check_email, name="check_email"),
    path("verify/<str:token>/", views.verify, name="verify"),
    path("verified/", views.verified, name="verified"),
    path("resend/", views.resend, name="resend"),
]
