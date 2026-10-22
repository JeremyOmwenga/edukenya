from django.urls import path

from . import views

app_name = "school"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.SchoolLoginView.as_view(), name="login"),
    path("logout/", views.school_logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
