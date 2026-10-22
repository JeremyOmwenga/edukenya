from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from accounts.models import User


class SchoolLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_("Email"), max_length=254,
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )
    error_messages = {
        "invalid_login": _("Incorrect email or password."),
        "inactive": _("Incorrect email or password."),
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def confirm_login_allowed(self, user):
        # Platform admins never exist in school schemas, but be explicit.
        if not user.is_active or user.role == User.Role.PLATFORM_ADMIN:
            raise forms.ValidationError(self.error_messages["invalid_login"], code="invalid_login")
