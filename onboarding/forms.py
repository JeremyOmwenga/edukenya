from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from accounts.models import User
from tenancy.counties import COUNTY_CHOICES
from tenancy.validators import validate_knec_code, validate_subdomain

from .services import knec_taken, subdomain_taken


class SchoolRegistrationForm(forms.Form):
    school_name = forms.CharField(label=_("School name"), max_length=200, min_length=3)
    knec_code = forms.CharField(
        label=_("KNEC school code"), max_length=8, min_length=8,
        help_text=_("The 8 digit code on your KNEC documents."),
        widget=forms.TextInput(attrs={"inputmode": "numeric", "pattern": r"\d{8}", "autocomplete": "off"}),
    )
    county = forms.ChoiceField(label=_("County"), choices=[("", _("Choose your county"))] + COUNTY_CHOICES)
    subdomain = forms.CharField(
        label=_("School web address"), max_length=30, min_length=3,
        help_text=_("Lowercase letters, numbers and hyphens. Example: greenhill"),
        widget=forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false", "autocapitalize": "none"}),
    )
    admin_full_name = forms.CharField(label=_("Your full name"), max_length=150,
                                      widget=forms.TextInput(attrs={"autocomplete": "name"}))
    admin_email = forms.EmailField(label=_("Your email"), max_length=254,
                                   widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    password1 = forms.CharField(label=_("Password"), strip=False,
                                help_text=_("At least 10 characters. Avoid common words."),
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label=_("Confirm password"), strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    # Honeypot: hidden from people with CSS and aria-hidden; bots tend to fill it.
    website = forms.CharField(required=False, label="Website",
                              widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def clean_knec_code(self):
        code = self.cleaned_data["knec_code"].strip()
        validate_knec_code(code)
        if knec_taken(code):
            raise ValidationError(_("A school with this KNEC code is already registered or waiting for approval."))
        return code

    def clean_subdomain(self):
        sub = self.cleaned_data["subdomain"].strip().lower()
        validate_subdomain(sub)
        if subdomain_taken(sub):
            raise ValidationError(_("This web address is taken. Please choose another."))
        return sub

    def clean_admin_email(self):
        return self.cleaned_data["admin_email"].strip().lower()

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", _("The two passwords do not match."))
        elif p1:
            probe = User(email=data.get("admin_email"), full_name=data.get("admin_full_name", ""))
            try:
                validate_password(p1, user=probe)
            except ValidationError as e:
                self.add_error("password1", e)
        return data

    @property
    def is_bot(self):
        return bool(self.data.get("website"))


class ResendVerificationForm(forms.Form):
    email = forms.EmailField(label=_("Your email"), max_length=254,
                             widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
