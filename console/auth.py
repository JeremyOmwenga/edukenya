from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import Http404

from accounts.models import User


def is_platform_admin(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.is_superuser
        and user.role == User.Role.PLATFORM_ADMIN
    )


def platform_admin_required(view):
    """
    Console guard. Only works on the root domain (public schema), and only for
    active platform super admins. Anyone else signed in gets a 404, not a hint
    that the page exists.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(request, "tenant", None) is None or request.tenant.schema_name != settings.PUBLIC_SCHEMA_NAME:
            raise Http404
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="/console/login/")
        if not is_platform_admin(request.user):
            raise Http404
        return view(request, *args, **kwargs)

    return wrapper
