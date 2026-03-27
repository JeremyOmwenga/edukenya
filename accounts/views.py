from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.core.mail import send_mail
from django.conf import settings

from .models import User, EmailVerificationToken
from .forms  import SignupForm, LoginForm


def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        print("POST data:", request.POST)        # see what was submitted
        print("Form valid:", form.is_valid())
        print("Form errors:", form.errors)       # see exactly what failed
        if form.is_valid():
            user = User.objects.create_user(
                email    = form.cleaned_data['email'],
                name     = form.cleaned_data['name'],
                password = form.cleaned_data['password'],
                role     = form.cleaned_data['role'],
            )

            token_value = EmailVerificationToken.generate()
            EmailVerificationToken.objects.create(user=user, token=token_value)

            verify_url = request.build_absolute_uri(
                f'/verify-email/?token={token_value}'
            )

            send_mail(
                subject    = 'Confirm your Elimu account',
                message    = (
                    f'Hi {user.name},\n\n'
                    f'Click the link below to confirm your email address:\n\n'
                    f'{verify_url}\n\n'
                    f'This link expires in 24 hours.\n\n'
                    f'If you did not sign up for Elimu, ignore this email.\n\n'
                    f'— The Elimu Team'
                ),
                from_email = settings.DEFAULT_FROM_EMAIL,
                recipient_list = [user.email],
                fail_silently  = False,
            )

            return redirect('check_email')
    else:
        form = SignupForm()

    return render(request, 'accounts/signup.html', {'form': form})


def check_email_view(request):
    return render(request, 'accounts/check_email.html')


def verify_email_view(request):
    token_value = request.GET.get('token', '')

    if not token_value:
        return render(request, 'accounts/verify_error.html',
                      {'message': 'No token provided.'})

    try:
        token = EmailVerificationToken.objects.select_related('user').get(
            token=token_value
        )
    except EmailVerificationToken.DoesNotExist:
        return render(request, 'accounts/verify_error.html',
                      {'message': 'This link is invalid or has already been used.'})

    from django.utils import timezone
    from datetime import timedelta
    if token.created_at < timezone.now() - timedelta(hours=24):
        token.delete()
        return render(request, 'accounts/verify_error.html',
                      {'message': 'This link has expired. Please sign up again.'})

    user = token.user
    user.is_active         = True
    user.is_email_verified = True
    user.save(update_fields=['is_active', 'is_email_verified'])
    token.delete()

    return redirect('login')


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            login(request, form.user)
            return redirect('dashboard')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'accounts/dashboard.html')
