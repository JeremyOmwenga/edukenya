from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from edukenya.security import client_ip, rate_limited
from onboarding import services
from onboarding.models import SchoolApplication
from tenancy.models import Client

from .audit import record
from .auth import platform_admin_required
from .forms import ConsoleLoginForm, ReasonForm, SchoolStatusForm
from .models import AuditEvent

S = SchoolApplication.Status


class ConsoleLoginView(LoginView):
    template_name = "console/login.html"
    authentication_form = ConsoleLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.tenant.schema_name != "public":
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if rate_limited("console_login_ip", client_ip(request)):
            return render(request, "console/login.html",
                          {"form": self.get_form(), "locked": True}, status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        record(form.get_user(), "console.login", ip=client_ip(self.request))
        return super().form_valid(form)

    def form_invalid(self, form):
        record(None, "console.login_failed", ip=client_ip(self.request),
               actor_email=(form.data.get("username") or "")[:254])
        return super().form_invalid(form)

    def get_default_redirect_url(self):
        return "/console/"


@require_POST
def console_logout(request):
    logout(request)
    return redirect("console:login")


@platform_admin_required
def home(request):
    counts = dict(SchoolApplication.objects.values_list("status").annotate(n=Count("id")))
    schools = Client.objects.exclude(schema_name="public")
    return render(request, "console/home.html", {
        "pending_review": counts.get(S.PENDING_REVIEW, 0),
        "pending_email": counts.get(S.PENDING_EMAIL, 0),
        "approved": counts.get(S.APPROVED, 0),
        "rejected": counts.get(S.REJECTED, 0),
        "active_schools": schools.filter(status=Client.Status.ACTIVE).count(),
        "suspended_schools": schools.filter(status=Client.Status.SUSPENDED).count(),
        "recent_events": AuditEvent.objects.all()[:10],
    })


@platform_admin_required
def applications(request):
    status = request.GET.get("status", S.PENDING_REVIEW)
    if status not in S.values:
        status = S.PENDING_REVIEW
    page = Paginator(SchoolApplication.objects.filter(status=status), 25).get_page(request.GET.get("page"))
    return render(request, "console/applications.html",
                  {"page": page, "status": status, "statuses": S.choices})


@platform_admin_required
def application_detail(request, pk):
    app = get_object_or_404(SchoolApplication, pk=pk)
    return render(request, "console/application_detail.html",
                  {"app": app, "reject_form": ReasonForm(), "can_decide": app.status == S.PENDING_REVIEW})


@platform_admin_required
@require_POST
def application_approve(request, pk):
    try:
        app = services.approve(pk, request.user, ip=client_ip(request))
    except services.ApplicationStateError as e:
        messages.error(request, str(e))
    except SchoolApplication.DoesNotExist:
        raise Http404
    else:
        messages.success(request, f"{app.school_name} approved. {app.full_domain} is live.")
    return redirect("console:application_detail", pk=pk)


@platform_admin_required
@require_POST
def application_reject(request, pk):
    app = get_object_or_404(SchoolApplication, pk=pk)
    form = ReasonForm(request.POST)
    if not form.is_valid():
        return render(request, "console/application_detail.html",
                      {"app": app, "reject_form": form, "can_decide": app.status == S.PENDING_REVIEW},
                      status=400)
    try:
        services.reject(pk, request.user, form.cleaned_data["reason"], ip=client_ip(request))
    except services.ApplicationStateError as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"{app.school_name} rejected. The admin has been emailed the reason.")
    return redirect("console:application_detail", pk=pk)


@platform_admin_required
def schools(request):
    page = Paginator(Client.objects.exclude(schema_name="public").prefetch_related("domains").order_by("name"),
                     25).get_page(request.GET.get("page"))
    return render(request, "console/schools.html", {"page": page, "status_form": SchoolStatusForm()})


@platform_admin_required
@require_POST
def school_set_status(request, pk, new_status):
    if new_status not in Client.Status.values:
        raise Http404
    form = SchoolStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please give a reason (at least 5 characters).")
        return redirect("console:schools")
    try:
        client = services.set_school_status(pk, request.user, new_status, form.cleaned_data["reason"],
                                            ip=client_ip(request))
    except services.ApplicationStateError as e:
        messages.error(request, str(e))
    except Client.DoesNotExist:
        raise Http404
    else:
        messages.success(request, f"{client.name} is now {client.get_status_display().lower()}.")
    return redirect("console:schools")


@platform_admin_required
def audit_log(request):
    page = Paginator(AuditEvent.objects.all(), 50).get_page(request.GET.get("page"))
    return render(request, "console/audit.html", {"page": page})
