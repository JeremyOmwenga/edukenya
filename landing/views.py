from django.shortcuts import render

def index(request):
    return render(request, 'landing/index.html')
def login_view(request):
    return render(request, 'landing/login.html')
def signup_view(request):
    return render(request, 'landing/signup.html')

