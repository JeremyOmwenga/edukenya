from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from edukenya.security import client_ip, rate_limited

from .forms import SchoolLoginForm


def _school_only(request):
    # Defense in depth: the tenant URLconf is never used for the public schema,
    # but never serve school pages without a school.
    if getattr(request, "tenant", None) is None or request.tenant.schema_name == settings.PUBLIC_SCHEMA_NAME:
        raise Http404


def home(request):
    _school_only(request)
    return redirect("school:dashboard" if request.user.is_authenticated else "school:login")


class SchoolLoginView(LoginView):
    template_name = "school/login.html"
    authentication_form = SchoolLoginForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        _school_only(request)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        account = (request.POST.get("username") or "").strip().lower()
        if rate_limited("login_ip", client_ip(request)) or (account and rate_limited("login_account", account)):
            return render(request, "school/login.html",
                          {"form": self.get_form(), "locked": True}, status=429)
        return super().post(request, *args, **kwargs)

    def get_default_redirect_url(self):
        return "/dashboard/"


@require_POST
def school_logout(request):
    _school_only(request)
    logout(request)
    return redirect("school:login")


@login_required
def dashboard(request):
    _school_only(request)
    return render(request, "school/dashboard.html")
