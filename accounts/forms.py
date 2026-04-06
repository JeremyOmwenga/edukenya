from django import forms
from django.contrib.auth import authenticate
from .models import User


class SignupForm(forms.Form):
    name     = forms.CharField(max_length=150)
    email    = forms.EmailField()
    password = forms.CharField(min_length=8, widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class LoginForm(forms.Form):
    email    = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email    = self.cleaned_data.get('email', '').lower()
        password = self.cleaned_data.get('password', '')

        if email and password:
            self.user = authenticate(username=email, password=password)
            if self.user is None:
                raise forms.ValidationError('Incorrect email or password.')
            if not self.user.is_active:
                raise forms.ValidationError(
                    'Please verify your email address before logging in.'
                )
        return self.cleaned_data
