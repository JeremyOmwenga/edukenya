from django.urls import path

from . import views

app_name = "console"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.ConsoleLoginView.as_view(), name="login"),
    path("logout/", views.console_logout, name="logout"),
    path("applications/", views.applications, name="applications"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/approve/", views.application_approve, name="application_approve"),
    path("applications/<int:pk>/reject/", views.application_reject, name="application_reject"),
    path("schools/", views.schools, name="schools"),
    path("schools/<int:pk>/<str:new_status>/", views.school_set_status, name="school_set_status"),
    path("audit/", views.audit_log, name="audit"),
]
