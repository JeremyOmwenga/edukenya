from django.urls import path
from accounts import views

urlpatterns = [
    path('signup/',       views.signup_view,      name='signup'),
    path('check-email/',  views.check_email_view, name='check_email'),
    path('verify-email/', views.verify_email_view, name='verify_email'),
    path('login/',        views.login_view,        name='login'),
    path('logout/',       views.logout_view,       name='logout'),
    path('dashboard/',    views.dashboard_view,    name='dashboard'),
]
