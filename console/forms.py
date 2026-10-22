from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .auth import is_platform_admin


class ConsoleLoginForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "Incorrect email or password.",
        "inactive": "Incorrect email or password.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def confirm_login_allowed(self, user):
        # Same message as a wrong password: do not reveal that the account exists.
        if not is_platform_admin(user):
            raise forms.ValidationError(self.error_messages["invalid_login"], code="invalid_login")


class ReasonForm(forms.Form):
    reason = forms.CharField(
        min_length=10, max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text="The school admin will see this in the email.",
    )


class SchoolStatusForm(forms.Form):
    reason = forms.CharField(min_length=5, max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))
